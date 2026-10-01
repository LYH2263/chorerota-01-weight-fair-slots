"""落库层测例：格子/快照持久化、失败原子性、快照不变性。"""

import pytest

from app import seed
from app.db import connect
from app.modules.weight import generate_week, get_board, TaskPlanError


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    seed.init_db()
    yield


def _assignment_count(c, week_id=1):
    return c.execute("SELECT COUNT(*) n FROM assignments WHERE week_id=?",
                     (week_id,)).fetchone()["n"]


def test_generation_persists_cells_and_snapshot(db):
    # 种子：3 名活跃 clean 成员；任务权重 洗碗1 / 倒垃圾1 / 扫地2，7 天 -> 28 格。
    slots = generate_week(1, days=7)
    assert len(slots) == 28
    c = connect()
    try:
        assert _assignment_count(c) == 28
        # 每行带 cell 与权重快照；扫地(weight=2)落 14 格，cell 覆盖 0/1。
        rows = c.execute(
            "SELECT cell, weight FROM assignments WHERE week_id=1 AND task_id=3 ORDER BY cell"
        ).fetchall()
        assert len(rows) == 14
        assert {r["weight"] for r in rows} == {2}
        assert {r["cell"] for r in rows} == {0, 1}
        # 周任务权重快照：仅入表的 3 个 clean 任务。
        snap = {r["task_id"]: r["weight"] for r in c.execute(
            "SELECT task_id, weight FROM week_task_snapshots WHERE week_id=1")}
        assert snap == {1: 1, 2: 1, 3: 2}
        assert c.execute("SELECT status FROM weeks WHERE id=1").fetchone()["status"] == "ready"
    finally:
        c.close()

    # 看板聚合的负荷之和等于总格数，且差 <=1。
    c = connect()
    try:
        board = get_board(c, 1)
    finally:
        c.close()
    loads = [w["slots"] for w in board["workload"]]
    assert sum(loads) == 28
    assert max(loads) - min(loads) <= 1
    assert {s["task_id"]: s["weight"] for s in board["snapshots"]} == {1: 1, 2: 1, 3: 2}


def test_non_positive_weight_fails_atomically(db):
    # 先成功生成一版。
    generate_week(1, days=7)
    c = connect()
    try:
        before = _assignment_count(c)
        # 新增一个 clean 且 weight=-1 的任务。
        c.execute("INSERT INTO tasks(title,weight,data_quality) VALUES (?,?,?)",
                  ("零权任务", -1, "clean"))
        c.commit()
    finally:
        c.close()

    with pytest.raises(TaskPlanError) as ei:
        generate_week(1, days=7)
    assert ei.value.reason == "non_positive_weight"

    c = connect()
    try:
        # 整次失败：行数与周状态保持生成前原值，未被清空/覆盖。
        assert _assignment_count(c) == before
        assert c.execute("SELECT status FROM weeks WHERE id=1").fetchone()["status"] == "ready"
    finally:
        c.close()


def test_snapshot_immutable_until_regenerated(db):
    generate_week(1, days=7)
    c = connect()
    try:
        # 事后把扫地权重从 2 改成 3，但不重新生成。
        c.execute("UPDATE tasks SET weight=3 WHERE id=3")
        c.commit()
        board = get_board(c, 1)
    finally:
        c.close()
    # 已生成周仍按快照 weight=2 / 28 格，不被新权重重切。
    assert len(board["assignments"]) == 28
    assert {a["weight"] for a in board["assignments"] if a["task_id"] == 3} == {2}
    assert {s["task_id"]: s["weight"] for s in board["snapshots"]} == {1: 1, 2: 1, 3: 2}

    # 重新生成同一周后才按新权重 3 重算（35 格），快照同步更新。
    slots = generate_week(1, days=7)
    assert len(slots) == 35
    c = connect()
    try:
        board = get_board(c, 1)
        snap = {s["task_id"]: s["weight"] for s in board["snapshots"]}
        assert len(board["assignments"]) == 35
        assert snap == {1: 1, 2: 1, 3: 3}
        assert {a["weight"] for a in board["assignments"] if a["task_id"] == 3} == {3}
    finally:
        c.close()


def test_missing_week_raises_lookup(db):
    with pytest.raises(LookupError):
        generate_week(999, days=7)
    c = connect()
    try:
        with pytest.raises(LookupError):
            get_board(c, 999)
    finally:
        c.close()
