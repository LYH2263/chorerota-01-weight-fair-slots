"""权重公平占格模块。

三件事分文件，互不混杂：
- ``expansion`` 权重口径（入表过滤 + 按权重展开多格）；
- ``balance``   余数策略（最低负荷成员优先、平票按 id）；
- ``snapshot``  落库与读取（生成事务、权重快照、看板/负荷聚合）。
"""

from .expansion import TaskPlanError, select_active_tasks, expand_cells
from .balance import assign_members
from .snapshot import build_weighted_slots, generate_week, get_board

__all__ = [
    "TaskPlanError",
    "select_active_tasks",
    "expand_cells",
    "assign_members",
    "build_weighted_slots",
    "generate_week",
    "get_board",
]
