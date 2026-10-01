"""落库与读取：生成事务、权重快照、看板聚合。触库，模块内唯一接触 sqlite 的地方。"""

from app.db import connect

from .expansion import select_active_tasks, expand_cells, TaskPlanError
from .balance import assign_members


def build_weighted_slots(member_ids: list[int], tasks: list[dict], days: int = 7) -> list[dict]:
    """权重口径 -> 展开多格 -> 余数策略派位，一条龙纯计算。"""
    if not member_ids:
        raise TaskPlanError("no_active_members")
    active = select_active_tasks(tasks)
    if not active:
        raise TaskPlanError("no_active_tasks")
    cells = expand_cells(active, days)  # days<=0 -> invalid_days
    return assign_members(cells, member_ids)


def generate_week(week_id: int, days: int = 7) -> list[dict]:
    """校验通过后在单事务内整周覆盖；任何写之前的校验失败都不会动旧行。"""
    c = connect()
    try:
        week = c.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
        if not week:
            raise LookupError("week not found")
        member_ids = [r["id"] for r in c.execute(
            "SELECT id FROM members WHERE active=1 AND data_quality='clean' ORDER BY id")]
        tasks = [dict(r) for r in c.execute(
            "SELECT id,title,weight,data_quality FROM tasks ORDER BY id")]
        # 纯计算：所有 guard（负权/脏过滤/空集/天数）在此触发，时尚无任何写操作。
        slots = build_weighted_slots(member_ids, tasks, days)
        _persist_week(c, week_id, slots)
        c.commit()
        return slots
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _persist_week(c, week_id: int, slots: list[dict]) -> None:
    """整周覆盖 assignments 与该周权重快照；不自行 commit（事务由调用方控制）。"""
    c.execute("DELETE FROM assignments WHERE week_id=?", (week_id,))
    c.execute("DELETE FROM week_task_snapshots WHERE week_id=?", (week_id,))
    c.executemany(
        "INSERT INTO assignments(week_id,day,task_id,cell,member_id,weight)"
        " VALUES (?,?,?,?,?,?)",
        [(week_id, s["day"], s["task_id"], s["cell"], s["member_id"], s["weight"])
         for s in slots],
    )
    weights = {}
    for s in slots:
        weights[s["task_id"]] = s["weight"]
    c.executemany(
        "INSERT INTO week_task_snapshots(week_id,task_id,weight) VALUES (?,?,?)",
        [(week_id, tid, w) for tid, w in weights.items()],
    )
    c.execute("UPDATE weeks SET status='ready' WHERE id=?", (week_id,))


def get_board(c, week_id: int) -> dict:
    """读周表：格位/权重一律以落库快照为准（不被后续改权重、改名穿透）。"""
    week = c.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not week:
        raise LookupError("week not found")
    assigns = [dict(r) for r in c.execute(
        """
        SELECT a.id, a.week_id, a.day, a.task_id, a.member_id,
               COALESCE(a.cell, 0) AS cell,
               COALESCE(a.weight, t.weight) AS weight,
               COALESCE(m.name, '?') AS member_name,
               COALESCE(t.title, '?') AS task_title
        FROM assignments a
        LEFT JOIN members m ON m.id = a.member_id
        LEFT JOIN tasks   t ON t.id = a.task_id
        WHERE a.week_id = ?
        ORDER BY a.day, a.task_id, COALESCE(a.cell, 0), a.id
        """, (week_id,))]
    snapshots = [dict(r) for r in c.execute(
        "SELECT task_id, weight FROM week_task_snapshots WHERE week_id=? ORDER BY task_id",
        (week_id,))]
    workload = [dict(r) for r in c.execute(
        """
        SELECT m.id AS member_id, m.name AS member_name, COUNT(a.id) AS slots
        FROM members m
        LEFT JOIN assignments a
               ON a.member_id = m.id AND a.week_id = ?
        WHERE m.active = 1 AND m.data_quality = 'clean'
        GROUP BY m.id
        ORDER BY m.id
        """, (week_id,))]
    return {"week": dict(week), "assignments": assigns,
            "snapshots": snapshots, "workload": workload}
