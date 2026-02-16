"""创意验证 Agent。"""
from __future__ import annotations

from core.base_agent import BaseAgent
from core.context import DecisionContext
from core.schemas import IDEA_VALIDATION_OUTPUT


# Mock 固定输出（符合 schema）
MOCK_OUTPUT = {
    "valid": True,
    "clarity_score": 7,
    "summary": "用户希望评估一项副业/创业方向的可行性，需结合市场与资源做决策。",
    "assumptions": ["以兼职或小规模启动为前提", "预算与时间有限"],
    "missing_info": ["具体行业或产品类型", "可投入时间与资金上限"],
    "suggested_refinement": "建议补充：目标行业、可接受风险等级、时间与资金约束。",
}


class IdeaValidatorAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("idea_validation", MOCK_OUTPUT)

    def _build_prompt(self, ctx: DecisionContext, view: dict) -> str:
        q = view.get("user_input", {}).get("question", "")
        bg = view.get("user_input", {}).get("background", "")
        return f"""你是一个创意验证 Agent，需要评估用户提出的创业/副业想法的清晰度和完整性。

用户问题: {q}
背景: {bg if bg else "未提供"}

请输出一个 JSON 对象，必须严格包含以下 6 个字段，不允许任何额外字段：

1. valid: bool（创意是否清晰有效）
2. clarity_score: int（清晰度评分，1-10）
3. summary: str（一句话总结，必须有内容，不能为空）
4. assumptions: list[str]（假设列表，至少 2 条，即使信息充足也要列出基本假设）
5. missing_info: list[str]（缺失信息列表，至少 2 条，即使信息充足也要列出可补充项）
6. suggested_refinement: str（建议补充方向，必须有内容）

重要约束：
- 只输出 JSON 对象，不要任何 Markdown、代码块（禁止 ```json）、自然语言解释或额外说明
- 禁止输出 "[skip]" 或空字符串
- assumptions 和 missing_info 必须至少各 2 条，不能为空数组
- summary 和 suggested_refinement 必须是有意义的文本，不能为空
- 输出前请自检：是否包含全部 6 个字段？字段类型是否正确？数组是否至少 2 条？字符串是否非空？

输出格式示例：
{{"valid": true, "clarity_score": 7, "summary": "用户希望评估副业可行性", "assumptions": ["以兼职方式启动", "预算有限"], "missing_info": ["具体行业", "时间投入"], "suggested_refinement": "建议补充行业和预算信息"}}"""
