"""Reflection Agent（无 rerun），仅做一致性检查与总结。
强制输出严格 JSON，不允许额外字段和自然语言解释。
"""
from __future__ import annotations

from typing import Any

from core.base_agent import BaseAgent
from core.context import DecisionContext
from core.schemas import REFLECTION_OUTPUT


MOCK_OUTPUT = {
    "consistency_check": True,
    "conflicts": [],
    "summary": "",
    "suggested_actions": [],
    "confidence_in_outputs": "中",
}


class ReflectorAgent(BaseAgent):
    """Reflector：输出必须严格匹配 REFLECTION_OUTPUT schema，无额外字段。"""

    # schema 定义的必需字段（按顺序）
    REQUIRED_FIELDS = ["consistency_check", "conflicts", "summary", "suggested_actions", "confidence_in_outputs"]
    VALID_CONFIDENCE = {"高", "中", "低"}

    def __init__(self) -> None:
        super().__init__("reflection", MOCK_OUTPUT)

    def run(self, ctx: DecisionContext) -> dict[str, Any]:
        """运行并严格过滤输出，确保只包含 schema 字段且类型正确。"""
        view = ctx.to_readonly_view()
        prompt = self._build_prompt(ctx, view)
        raw_output = self.llm.complete(prompt, view)
        return self._strict_filter(raw_output)

    def _strict_filter(self, raw: dict[str, Any]) -> dict[str, Any]:
        """
        严格过滤：只保留 schema 字段，确保类型正确。
        若无法判断或字段不合法，返回默认合法结构。
        """
        result = dict(REFLECTION_OUTPUT)
        default = dict(MOCK_OUTPUT)

        # 1. consistency_check: bool
        if isinstance(raw.get("consistency_check"), bool):
            result["consistency_check"] = raw["consistency_check"]
        else:
            result["consistency_check"] = default["consistency_check"]

        # 2. conflicts: list[str]（至少 1 条）
        conflicts_raw = raw.get("conflicts")
        if isinstance(conflicts_raw, list):
            conflicts_filtered = [str(item) for item in conflicts_raw if item]
            if len(conflicts_filtered) >= 1:
                result["conflicts"] = conflicts_filtered
            else:
                result["conflicts"] = ["各阶段结论一致，无冲突"]  # 至少 1 条
        else:
            result["conflicts"] = ["各阶段结论一致，无冲突"]  # 至少 1 条

        # 3. summary: str（必须有内容）
        summary_raw = raw.get("summary")
        if isinstance(summary_raw, str) and summary_raw.strip() and summary_raw.strip() != "[skip]":
            result["summary"] = summary_raw.strip()
        else:
            result["summary"] = "各阶段输出一致，建议谨慎推进" if not default["summary"] else default["summary"]

        # 4. suggested_actions: list[str]（至少 2 条）
        actions_raw = raw.get("suggested_actions")
        if isinstance(actions_raw, list):
            actions_filtered = [str(item) for item in actions_raw if item]
            if len(actions_filtered) >= 2:
                result["suggested_actions"] = actions_filtered
            else:
                # 不足 2 条时补充默认项
                result["suggested_actions"] = actions_filtered + ["补充具体行业与预算后再跑一轮", "设定 3 个月复盘节点"][:2 - len(actions_filtered)]
        else:
            result["suggested_actions"] = ["补充具体行业与预算后再跑一轮", "设定 3 个月复盘节点"]

        # 5. confidence_in_outputs: "高"/"中"/"低"
        conf_raw = raw.get("confidence_in_outputs")
        if isinstance(conf_raw, str) and conf_raw.strip() in self.VALID_CONFIDENCE:
            result["confidence_in_outputs"] = conf_raw.strip()
        else:
            result["confidence_in_outputs"] = default["confidence_in_outputs"]

        return result

    def _build_prompt(self, ctx: DecisionContext, view: dict[str, Any]) -> str:
        """构建 prompt，强调只输出严格 JSON，无额外字段和自然语言。"""
        q = view.get("user_input", {}).get("question", "")
        stages_info = []
        for sid in view.get("stages_order", []):
            stage_data = view.get("stages", {}).get(sid, {})
            if stage_data:
                stages_info.append(f"{sid}: {stage_data}")

        return f"""你是一个反思 Agent，需要检查决策引擎各阶段输出的一致性。

用户问题: {q}

已有阶段输出:
{chr(10).join(stages_info) if stages_info else "无"}

请分析并输出一个 JSON 对象，必须严格包含以下 5 个字段，不允许任何额外字段：

1. consistency_check: bool（是否一致，必须是 true 或 false）
2. conflicts: list[str]（冲突列表，至少 1 条，即使无冲突也要给出 1 条解释性说明，如："各阶段结论一致" 或 "创意验证与市场分析存在矛盾"）
3. summary: str（总结，简洁一句话，必须有内容，不能为空）
4. suggested_actions: list[str]（建议动作列表，至少 2 条）
5. confidence_in_outputs: str（只能是 '高'、'中'、'低' 之一）

重要约束：
- 只输出 JSON 对象，不要任何 Markdown、代码块（禁止 ```json）、自然语言解释或额外说明
- 禁止输出 "[skip]" 或空字符串
- consistency_check 必须是布尔值 true 或 false，不能是字符串
- conflicts 必须至少 1 条，即使无冲突也要给出解释性条目（如："各阶段结论一致，无冲突"）
- summary 必须是有意义的文本，不能为空
- suggested_actions 必须至少 2 条，不能为空数组
- confidence_in_outputs 必须是 "高"、"中"、"低" 之一
- 输出前请自检：是否包含全部 5 个字段？字段类型是否正确？consistency_check 是否为 bool？conflicts 是否至少 1 条？suggested_actions 是否至少 2 条？summary 是否非空？

输出格式示例：
{{"consistency_check": true, "conflicts": ["各阶段结论一致"], "summary": "结论一致", "suggested_actions": ["建议1", "建议2"], "confidence_in_outputs": "中"}}"""
