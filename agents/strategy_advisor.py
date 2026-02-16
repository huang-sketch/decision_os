"""策略建议 Agent（含风险与资源逻辑，扁平化、无浮点）。"""
from __future__ import annotations

from core.base_agent import BaseAgent
from core.context import DecisionContext
from core.schemas import STRATEGY_ADVICE_OUTPUT


MOCK_OUTPUT = {
    "verdict": "谨慎做",
    "confidence": "中",
    "reasons": ["市场有机会但竞争不低", "需控制投入与节奏"],
    "overall_risk_level": "中",
    "risk_factors": [
        {"name": "现金流", "level": "中", "mitigation": "先小规模验证再放大"},
        {"name": "时间分配", "level": "高", "mitigation": "设定每周固定投入上限"},
    ],
    "max_loss_estimate": "建议控制在可承受损失的范围内试水",
    "reversibility": "部分可逆",
    "risk_recommendation": "谨慎继续",
    "time_estimate": "建议 6 个月内以兼职方式验证",
    "budget_estimate": "视项目而定，建议预留 3–6 个月生活备用金",
    "key_milestones": [
        {"phase": "验证", "duration": "1–2 月", "deliverable": "MVP 或小规模试点"},
        {"phase": "放大", "duration": "3–6 月", "deliverable": "稳定收入或明确止损"},
    ],
    "critical_resources": ["时间", "启动资金", "技能或合作"],
    "gaps": ["需明确获客与交付能力"],
    "action_items": [
        {"priority": "高", "action": "明确目标客户与价值主张", "timeline": "2 周内"},
        {"priority": "中", "action": "做一次小规模试点", "timeline": "1 个月内"},
    ],
    "alternatives": ["先做咨询/顾问类轻资产", "与现有工作结合做内部创业"],
    "one_liner": "可谨慎尝试，先小步验证再决定是否加大投入。",
}


class StrategyAdvisorAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("strategy_advice", MOCK_OUTPUT)

    def _build_prompt(self, ctx: DecisionContext, view: dict) -> str:
        q = view.get("user_input", {}).get("question", "")
        idea_stage = view.get("stages", {}).get("idea_validation", {})
        market_stage = view.get("stages", {}).get("market_analysis", {})
        idea_valid = idea_stage.get("valid", True)
        market_trend = market_stage.get("trend", "")
        market_competition = market_stage.get("competition_level", "")
        
        verdict_rule = ""
        if idea_valid is False:
            verdict_rule = "\n重要：如果 idea_validation.valid == false，则 verdict 必须为 \"暂缓\"。"
        
        return f"""你是一个策略建议 Agent，需要综合创意验证和市场分析结果，给出最终决策建议。

用户问题: {q}
创意验证: valid={idea_valid}, summary={idea_stage.get("summary", "")}
市场分析: trend={market_trend}, competition_level={market_competition}

请输出一个 JSON 对象，必须严格包含以下 17 个字段，不允许任何额外字段：

1. verdict: str（建议做/谨慎做/暂缓/不建议做）{verdict_rule}
2. confidence: str（高/中/低）
3. reasons: list[str]（原因列表，至少 2 条）
4. overall_risk_level: str（低/中/高）
5. risk_factors: list[dict]（每个 dict 含 name/level/mitigation，至少 1 条）
6. max_loss_estimate: str（最大损失估计）
7. reversibility: str（可逆性：可逆/部分可逆/不可逆）
8. risk_recommendation: str（风险建议）
9. time_estimate: str（时间估计）
10. budget_estimate: str（预算估计）
11. key_milestones: list[dict]（每个 dict 含 phase/duration/deliverable，至少 1 条）
12. critical_resources: list[str]（关键资源列表）
13. gaps: list[str]（缺口列表）
14. action_items: list[dict]（每个 dict 含 priority/action/timeline，至少 3 条，且 action 应为补充信息/验证动作，如：访谈目标用户、竞品分析、最小验证MVP）
15. alternatives: list[str]（替代方案列表）
16. one_liner: str（一句话结论，必须有内容，不能为空）

重要约束：
- 只输出 JSON 对象，不要任何 Markdown、代码块（禁止 ```json）、自然语言解释或额外说明
- 禁止输出 "[skip]" 或空字符串
- reasons 必须至少 2 条
- action_items 必须至少 3 条，且每条 action 应为具体的补充信息或验证动作（如：访谈5个目标用户、分析3个竞品、做最小验证MVP）
- one_liner 必须是有意义的文本，不能为空
- 输出前请自检：是否包含全部 17 个字段？字段类型是否正确？必需字段是否非空？数组是否满足最小数量要求？

输出格式示例（部分字段）：
{{"verdict": "谨慎做", "confidence": "中", "reasons": ["原因1", "原因2"], "action_items": [{{"priority": "高", "action": "访谈目标用户", "timeline": "2周内"}}, {{"priority": "中", "action": "竞品分析", "timeline": "1个月内"}}, {{"priority": "高", "action": "最小验证MVP", "timeline": "1个月内"}}], "one_liner": "可谨慎尝试"}}"""
