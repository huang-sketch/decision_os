"""
冷静度评估（纯规则引擎，不调用 LLM）。
4 个行为问题 → calm_score / calm_level / cooldown_tip / action_mode_adjustment。
"""
from __future__ import annotations

from typing import Any

_DIRECTION_PENALTY = {"从不": 0, "偶尔": 12, "经常": 28}
_IMPULSE_PENALTY = {"没有": 0, "偶尔": 14, "经常": 30}
_CONSUME_PENALTY = {"很少": 0, "有时": 10, "经常": 22}
_STOPLOSS_PENALTY = {"有": 0, "模糊": 10, "没有": 20}

_TIPS = {
    "high": "状态良好，可以推进关键决策。",
    "medium": "建议先做 7 天理性成长计划，降低冲动决策风险。",
    "low": "当前不适合做重大决策，建议先休整 + 执行 7 天冷静计划。",
}

_ACTION_ADJ = {
    "high": None,
    "medium": "试错",
    "low": "暂缓",
}

_ACTION_DOWNGRADE = {"执行": "试错", "做": "试错", "试错": "暂缓", "谨慎": "暂缓"}


def evaluate_calm(inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    规则评分。

    Parameters
    ----------
    inputs : dict, optional
        keys: direction_change, impulse, consume_vs_act, stop_loss
        缺失 key 用最优默认值（保证不填也能跑）。

    Returns
    -------
    dict with: calm_score (0-100), calm_level (high/medium/low),
               cooldown_tip (str), action_mode_adjustment (str|None)
    """
    inp = inputs or {}
    penalty = 0
    penalty += _DIRECTION_PENALTY.get(inp.get("direction_change", "从不"), 0)
    penalty += _IMPULSE_PENALTY.get(inp.get("impulse", "没有"), 0)
    penalty += _CONSUME_PENALTY.get(inp.get("consume_vs_act", "很少"), 0)
    penalty += _STOPLOSS_PENALTY.get(inp.get("stop_loss", "有"), 0)
    score = max(0, min(100, 100 - penalty))

    if score >= 70:
        level = "high"
    elif score >= 40:
        level = "medium"
    else:
        level = "low"

    return {
        "calm_score": score,
        "calm_level": level,
        "cooldown_tip": _TIPS[level],
        "action_mode_adjustment": _ACTION_ADJ[level],
    }


def apply_calm_to_recommendation(recommendation: str, calm_level: str) -> str:
    """若 calm_level 不佳，将 recommendation 降级（medium 降一级，low 降两级）。"""
    if calm_level == "high":
        return recommendation
    result = _ACTION_DOWNGRADE.get(recommendation, recommendation)
    if calm_level == "low":
        result = _ACTION_DOWNGRADE.get(result, "暂缓")
    return result
