"""市场分析 Agent。"""
from __future__ import annotations

from core.base_agent import BaseAgent
from core.context import DecisionContext
from core.schemas import MARKET_ANALYSIS_OUTPUT


MOCK_OUTPUT = {
    "market_size_estimate": "中",
    "trend": "上升",
    "competition_level": "中",
    "key_competitors": ["竞品A", "竞品B"],
    "opportunity_summary": "需求稳定增长，差异化与执行力是关键机会。",
    "risks": ["价格战", "政策变化"],
}


class MarketAnalyzerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("market_analysis", MOCK_OUTPUT)

    def _build_prompt(self, ctx: DecisionContext, view: dict) -> str:
        q = view.get("user_input", {}).get("question", "")
        idea_stage = view.get("stages", {}).get("idea_validation", {})
        idea_summary = idea_stage.get("summary", "")
        return f"""你是一个市场分析 Agent，需要分析用户提出的创业/副业想法的市场情况。

用户问题: {q}
创意验证结果: {idea_summary if idea_summary else "未提供"}

请输出一个 JSON 对象，必须严格包含以下 6 个字段，不允许任何额外字段：

1. market_size_estimate: str（市场规模：小/中/大）
2. trend: str（趋势：上升/平稳/下降，必须有内容）
3. competition_level: str（竞争水平：低/中/高，必须有内容）
4. key_competitors: list[str]（主要竞品列表，至少 1 条）
5. opportunity_summary: str（机会总结，必须有内容，不能为空）
6. risks: list[str]（风险列表，至少 2 条）

重要约束：
- 只输出 JSON 对象，不要任何 Markdown、代码块（禁止 ```json）、自然语言解释或额外说明
- 禁止输出 "[skip]" 或空字符串
- trend、competition_level、opportunity_summary 必须是有意义的文本，不能为空
- risks 必须至少 2 条，不能为空数组
- 输出前请自检：是否包含全部 6 个字段？字段类型是否正确？必需字段是否非空？risks 是否至少 2 条？

输出格式示例：
{{"market_size_estimate": "中", "trend": "上升", "competition_level": "中", "key_competitors": ["竞品A"], "opportunity_summary": "需求增长但竞争激烈", "risks": ["价格战", "政策变化"]}}"""
