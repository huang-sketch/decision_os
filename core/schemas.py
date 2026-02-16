"""
4 Agent 的 JSON Schema 定义（v0.1）。
Strategy 扁平化、无浮点；Reflector 无 rerun。
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 1. Idea Validator
# ---------------------------------------------------------------------------
IDEA_VALIDATION_OUTPUT = {
    "valid": True,
    "clarity_score": 5,
    "summary": "",
    "assumptions": [],
    "missing_info": [],
    "suggested_refinement": "",
}

def validate_idea_output(data: dict[str, Any]) -> bool:
    required = {"valid", "clarity_score", "summary", "assumptions", "missing_info", "suggested_refinement"}
    return required.issubset(data.keys()) and isinstance(data["clarity_score"], int)

# ---------------------------------------------------------------------------
# 2. Market Analyzer
# ---------------------------------------------------------------------------
MARKET_ANALYSIS_OUTPUT = {
    "market_size_estimate": "",
    "trend": "",
    "competition_level": "",
    "key_competitors": [],
    "opportunity_summary": "",
    "risks": [],
}

def validate_market_output(data: dict[str, Any]) -> bool:
    required = {"market_size_estimate", "trend", "competition_level", "key_competitors", "opportunity_summary", "risks"}
    return required.issubset(data.keys())

# ---------------------------------------------------------------------------
# 3. Strategy Advisor（扁平化、无浮点）
# ---------------------------------------------------------------------------
STRATEGY_ADVICE_OUTPUT = {
    "verdict": "",
    "confidence": "",  # 高/中/低
    "reasons": [],
    "overall_risk_level": "",
    "risk_factors": [],
    "max_loss_estimate": "",
    "reversibility": "",
    "risk_recommendation": "",
    "time_estimate": "",
    "budget_estimate": "",
    "key_milestones": [],
    "critical_resources": [],
    "gaps": [],
    "action_items": [],
    "alternatives": [],
    "one_liner": "",
}

def validate_strategy_output(data: dict[str, Any]) -> bool:
    required = {
        "verdict", "confidence", "reasons", "overall_risk_level", "risk_factors",
        "max_loss_estimate", "reversibility", "risk_recommendation",
        "time_estimate", "budget_estimate", "key_milestones", "critical_resources", "gaps",
        "action_items", "alternatives", "one_liner",
    }
    return required.issubset(data.keys())

# ---------------------------------------------------------------------------
# 4. Reflector（无 rerun）
# ---------------------------------------------------------------------------
REFLECTION_OUTPUT = {
    "consistency_check": True,
    "conflicts": [],
    "summary": "",
    "suggested_actions": [],
    "confidence_in_outputs": "",  # 高/中/低
}

def validate_reflection_output(data: dict[str, Any]) -> bool:
    required = {"consistency_check", "conflicts", "summary", "suggested_actions", "confidence_in_outputs"}
    return required.issubset(data.keys())

# 统一校验入口
VALIDATORS = {
    "idea_validation": validate_idea_output,
    "market_analysis": validate_market_output,
    "strategy_advice": validate_strategy_output,
    "reflection": validate_reflection_output,
}

def validate_stage_output(stage_id: str, data: dict[str, Any]) -> bool:
    fn = VALIDATORS.get(stage_id)
    return fn(data) if fn else False
