"""
DecisionContext: 统一数据容器，全流程唯一持有者。
v0.1: 无 reflection_history / next_stage_override，无 config/ 目录。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DecisionContext:
    """决策引擎统一上下文。"""

    # 稳定字段
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    scenario: str = "startup_side_business"
    version: str = "0.1"
    user_input: dict[str, Any] = field(default_factory=lambda: {"question": "", "background": "", "constraints": []})
    config: dict[str, Any] = field(default_factory=lambda: {"max_retries": 2, "degradation": "skip"})
    status: str = "pending"  # pending | running | completed | failed | partial
    error: dict[str, Any] | None = None

    # 可扩展：4 个 stage
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    stages_order: list[str] = field(
        default_factory=lambda: ["idea_validation", "market_analysis", "strategy_advice"]
    )
    current_stage: str | None = None

    # Reflection（仅最后一次结果）
    reflection: dict[str, Any] | None = None

    # 扩展
    extra: dict[str, Any] = field(default_factory=dict)

    def get_stage(self, stage_id: str) -> dict[str, Any] | None:
        return self.stages.get(stage_id)

    def set_stage(self, stage_id: str, output: dict[str, Any]) -> None:
        self.stages[stage_id] = output

    def to_readonly_view(self) -> dict[str, Any]:
        """只读视图，供 Agent 读取（不暴露可变引用）。"""
        return {
            "id": self.id,
            "scenario": self.scenario,
            "version": self.version,
            "user_input": dict(self.user_input),
            "stages": {k: dict(v) for k, v in self.stages.items()},
            "stages_order": list(self.stages_order),
            "reflection": dict(self.reflection) if self.reflection else None,
        }
