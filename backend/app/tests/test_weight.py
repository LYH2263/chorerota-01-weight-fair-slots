"""权重口径 / 余数策略的纯函数测例。"""

import pytest

from app.engines.rota import build_week_slots
from app.modules.weight import (
    TaskPlanError,
    select_active_tasks,
    build_weighted_slots,
)


def _task(tid, weight, dq="clean"):
    return {"id": tid, "title": f"T{tid}", "weight": weight, "data_quality": dq}


# 1) 等权回退：weight 全为 1 时与改造前 round-robin 逐格一致。
def test_equal_weight_falls_back_to_legacy_round_robin():
    members, tasks, days = [1, 2, 3], [_task(10, 1), _task(20, 1)], 7
    new = build_weighted_slots(members, tasks, days)
    old = build_week_slots(members, [10, 20], days=days)
    assert len(new) == len(old) == 14
    for n, o in zip(new, old):
        assert (n["day"], n["task_id"], n["member_id"]) == \
               (o["day"], o["task_id"], o["member_id"])
    # 每格仍带权重快照与 cell 序号。
    assert all(s["weight"] == 1 and s["cell"] == 0 for s in new)


# 2) 加权增格：任务按权重占多格，cell 区分同位多格。
def test_weighted_task_occupies_more_cells():
    tasks = [_task(10, 1), _task(20, 2)]
    slots = build_weighted_slots([1, 2, 3], tasks, days=7)
    assert len(slots) == 7 * (1 + 2) == 21
    t10 = [s for s in slots if s["task_id"] == 10]
    t20 = [s for s in slots if s["task_id"] == 20]
    assert len(t10) == 7 and len(t20) == 14
    assert {s["cell"] for s in t20} == {0, 1}
    # 每个 (day, cell) 组合唯一，且权重快照随格落定。
    assert all(s["weight"] == 2 for s in t20)
    keys = {(s["day"], s["task_id"], s["cell"]) for s in slots}
    assert len(keys) == len(slots)


# 3) 余数口径：格数差 <=1，余数归当前最低负荷者、平票按 id 升序。
def test_remainder_goes_to_lowest_load_then_lowest_id():
    # M=3, 权重和=4, days=1 -> N=4, r=1。
    slots = build_weighted_slots([1, 2, 3],
                                 [_task(10, 1), _task(20, 1), _task(30, 2)], days=1)
    loads = {m: 0 for m in (1, 2, 3)}
    for s in slots:
        loads[s["member_id"]] += 1
    assert len(slots) == 4
    assert max(loads.values()) - min(loads.values()) <= 1
    # 第 4 格（余数）在三人各 1 格后平票，归 id 最小者 1。
    assert slots[-1]["member_id"] == 1
    assert loads == {1: 2, 2: 1, 3: 1}

    # 成员顺序反转（等价于 id 序反转）时余数改归该序列最前者，钉死「平票按 id」。
    rev = build_weighted_slots([3, 2, 1],
                               [_task(10, 1), _task(20, 1), _task(30, 2)], days=1)
    assert rev[-1]["member_id"] == 3
    rev_loads = {m: sum(1 for s in rev if s["member_id"] == m) for m in (3, 2, 1)}
    assert max(rev_loads.values()) - min(rev_loads.values()) <= 1


# 4) 负权拒写（算法层）与脏任务排除。
def test_clean_non_positive_weight_rejected():
    with pytest.raises(TaskPlanError) as ei:
        select_active_tasks([_task(10, 0)])
    assert ei.value.reason == "non_positive_weight"
    with pytest.raises(TaskPlanError):
        select_active_tasks([_task(10, -1)])


def test_dirty_tasks_excluded_silently():
    # 脏任务即便负权也只是排除，不阻断；clean 任务正常入表。
    active = select_active_tasks([_task(9, -1, "dirty"), _task(10, 1, "clean")])
    assert [t["id"] for t in active] == [10]
    # 仅脏任务 -> 无有效任务 -> 生成期 no_active_tasks。
    with pytest.raises(TaskPlanError) as ei:
        build_weighted_slots([1], [_task(9, -1, "dirty")], days=7)
    assert ei.value.reason == "no_active_tasks"


def test_guard_reasons():
    with pytest.raises(TaskPlanError) as ei:
        build_weighted_slots([], [_task(10, 1)], days=7)
    assert ei.value.reason == "no_active_members"
    with pytest.raises(TaskPlanError) as ei:
        build_weighted_slots([1], [_task(10, 1)], days=0)
    assert ei.value.reason == "invalid_days"
