"""
串行调度 + 反思仅最后一次。
v0.1: 无 rerun 逻辑，Reflector 仅在全部 stage 结束后执行一次。
"""
from __future__ import annotations

from .context import DecisionContext
from .schemas import (
    REFLECTION_OUTPUT,
    IDEA_VALIDATION_OUTPUT,
    MARKET_ANALYSIS_OUTPUT,
    STRATEGY_ADVICE_OUTPUT,
    validate_stage_output,
)


# 默认输出（降级时使用）
_DEFAULT_OUTPUTS = {
    "idea_validation": {**IDEA_VALIDATION_OUTPUT, "valid": False, "summary": "[skip]"},
    "market_analysis": {**MARKET_ANALYSIS_OUTPUT, "opportunity_summary": "[skip]"},
    "strategy_advice": {**STRATEGY_ADVICE_OUTPUT, "verdict": "暂缓", "one_liner": "[skip]"},
    "reflection": {**REFLECTION_OUTPUT, "summary": "[skip]", "consistency_check": False},
}


class Engine:
    """串行执行 stages_order，最后执行一次 Reflector。"""

    def __init__(self, agent_registry: dict[str, "BaseAgent"], reflector: "BaseAgent"):
        self.agent_registry = agent_registry
        self.reflector = reflector

    def run(self, ctx: DecisionContext) -> DecisionContext:
        ctx.status = "running"
        max_retries = ctx.config.get("max_retries", 2)
        degradation = ctx.config.get("degradation", "skip")

        for stage_id in ctx.stages_order:
            ctx.current_stage = stage_id
            agent = self.agent_registry.get(stage_id)
            if not agent:
                ctx.stages[stage_id] = _DEFAULT_OUTPUTS.get(stage_id, {})
                continue

            last_error = None
            for attempt in range(max_retries):
                try:
                    out = agent.run(ctx)
                    if validate_stage_output(stage_id, out):
                        ctx.set_stage(stage_id, out)
                        break
                except Exception as e:
                    last_error = {"stage": stage_id, "attempt": attempt + 1, "message": str(e)}
            else:
                if degradation == "skip":
                    ctx.set_stage(stage_id, dict(_DEFAULT_OUTPUTS.get(stage_id, {})))
                else:
                    ctx.status = "failed"
                    ctx.error = last_error
                    return ctx

        # 仅在此处执行一次 Reflector
        ctx.current_stage = "reflection"
        try:
            reflection_out = self.reflector.run(ctx)
            if validate_stage_output("reflection", reflection_out):
                ctx.reflection = reflection_out
        except Exception as e:
            ctx.reflection = {**_DEFAULT_OUTPUTS["reflection"], "summary": f"[reflection error] {e}"}

        ctx.current_stage = None
        ctx.status = "completed"
        return ctx


# 类型注解用（避免循环导入）
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .base_agent import BaseAgent
