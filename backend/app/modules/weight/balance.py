"""余数策略：把展开后的格子派给成员。纯函数，不触库。

口径（已拍板）：每格都派给「当前已分格子数最少」的成员，平票按成员 id 升序
（``member_ids`` 由调用方按 id 升序给出）。

这与「先 N//M 轮严格轮转、再把余数格补给最低负荷者」严格等价：每完成完整一轮后
各人负荷相等，平票必然落到 id 最小的未补余成员。因此：
- 各人格数差恒 <= 1；
- weight 全为 1 时，派位结果与旧 ``build_week_slots`` 的 round-robin 逐格一致。
"""

from .expansion import TaskPlanError


def assign_members(cells: list[dict], member_ids: list[int]) -> list[dict]:
    if not member_ids:
        raise TaskPlanError("no_active_members")
    if not cells:
        raise TaskPlanError("no_active_tasks")
    loads = [0] * len(member_ids)
    slots = []
    for cell in cells:
        # (当前格数, id 序下标) 取最小：最低负荷优先，平票 id 靠前者先得。
        pick = min(range(len(member_ids)), key=lambda i: (loads[i], i))
        loads[pick] += 1
        slots.append({**cell, "member_id": member_ids[pick]})
    return slots
