"""权重口径：哪些任务入表、任务如何按权重展开成多格。纯函数，不触库。"""


class TaskPlanError(ValueError):
    """入表前校验失败。``reason`` 为机器可读的错误码。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def select_active_tasks(tasks: list[dict]) -> list[dict]:
    """取 clean 且 weight>0 的任务（输入应已按 id 升序）。

    - 非 clean（脏）任务：直接排除，不阻断生成；
    - clean 但 weight<=0：整次生成不可入表，抛 ``non_positive_weight``。
    """
    active = []
    for t in tasks:
        if t.get("data_quality") != "clean":
            continue
        if int(t["weight"]) <= 0:
            raise TaskPlanError("non_positive_weight")
        active.append(t)
    return active


def expand_cells(active_tasks: list[dict], days: int) -> list[dict]:
    """按「天 -> 任务(id 升序) -> 格序号」把任务按权重展开为格子。

    weight=1 时产出的 (day,task_id) 序列与改造前完全一致；
    同一 (day,task) 的多格用 ``cell ∈ [0, weight)`` 区分，每格自带权重快照。
    """
    if days <= 0:
        raise TaskPlanError("invalid_days")
    cells = []
    for day in range(days):
        for t in active_tasks:
            w = int(t["weight"])
            for cell in range(w):
                cells.append({"day": day, "task_id": t["id"], "cell": cell, "weight": w})
    return cells
