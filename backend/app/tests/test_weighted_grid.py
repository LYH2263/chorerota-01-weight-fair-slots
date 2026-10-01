"""加权占格纯引擎/模块测例：等权回退、加权增格、余数口径、负权拒写。"""
import pytest

from app.engines.rota import build_week_slots, WeightError, workloads
from app.modules.weighted_grid import plan_week, WeightValidationError
from app.modules.weighted_grid.remainder import POLICY, assign_with_remainder
from app.modules.weighted_grid.weights import coerce_int, as_int


def _old_layout(member_ids, task_ids, days=7):
    """改造前的参考实现，逐格对比用。"""
    slots, idx = [], 0
    for day in range(days):
        for tid in task_ids:
            slots.append({"day": day, "task_id": tid, "member_id": member_ids[idx % len(member_ids)]})
            idx += 1
    return slots


def test_equal_weight_falls_back_to_legacy_grid():
    """权重全 1：同成员同任务同天数与改造前逐格一致。"""
    got = build_week_slots([1, 2, 3], {10: 1, 20: 1}, days=7)
    want = _old_layout([1, 2, 3], [10, 20], 7)
    assert len(got) == len(want)
    for g, w in zip(got, want):
        assert g["day"] == w["day"] and g["task_id"] == w["task_id"]
        assert g["member_id"] == w["member_id"] and g["slot_index"] == 0


def test_legacy_list_signature_still_works():
    got = build_week_slots([1, 2, 3], [10, 20], days=2)
    assert [(s["day"], s["task_id"], s["member_id"]) for s in got] == [
        (0, 10, 1), (0, 20, 2), (1, 10, 3), (1, 20, 1)]


def test_weighted_expands_cells():
    """weight=2 的任务每日占两格；总格子 = days*sum(weights)。"""
    slots = build_week_slots([1, 2, 3], {10: 2, 20: 1}, days=7)
    assert len(slots) == 7 * 3
    per_task = {10: 0, 20: 0}
    for s in slots:
        per_task[s["task_id"]] += 1
    assert per_task == {10: 14, 20: 7}
    # 每日格身份：10 占 slot 0/1，20 占 slot 0
    day0 = [(s["task_id"], s["slot_index"]) for s in slots if s["day"] == 0]
    assert day0 == [(10, 0), (10, 1), (20, 0)]


def test_remainder_goes_to_lowest_load_and_balances_within_one():
    """14 格 / 3 人：基段每人 4，余数 2 格给负荷最低者 → 5/5/4。"""
    slots = build_week_slots([1, 2, 3], {10: 1, 20: 1}, days=7)
    loads = workloads(slots, [1, 2, 3])
    assert sorted(loads.values()) == [4, 5, 5]
    assert max(loads.values()) - min(loads.values()) <= 1
    # 余数格（base 之后）按当前最低负荷 + id 升序：先给 1 再给 2
    assert POLICY == "lowest_current_load"
    assert slots[12]["member_id"] == 1
    assert slots[13]["member_id"] == 2


def test_remainder_directly():
    cells = [{"day": 0, "task_id": 10, "slot_index": i} for i in range(5)]
    slots = assign_with_remainder(cells, [7, 8])  # 5 格/2 人 → 3/2，小 id 多
    assert workloads(slots, [7, 8]) == {7: 3, 8: 2}


def test_negative_and_zero_weight_rejected():
    with pytest.raises(WeightError):
        build_week_slots([1, 2], {10: -1, 20: 1})
    with pytest.raises(WeightError):
        build_week_slots([1, 2], {10: 0})


def test_plan_week_rejects_whole_generation_on_non_positive_clean_task():
    """任一 clean 任务 weight<=0 → 整次 plan 失败，不产出任何格子。"""
    rows = [{"id": 10, "weight": 2}, {"id": 20, "weight": -1}]
    with pytest.raises(WeightValidationError):
        plan_week([1, 2], rows, days=7)


def test_weight_coercion_rules():
    assert coerce_int(3) == 3
    assert as_int(0) == 0 and as_int(-2) == -2
    for bad in (0, -1, 1.5, "x", None, True):
        with pytest.raises((WeightValidationError, TypeError)):
            coerce_int(bad)
    assert as_int(2.0) == 2
