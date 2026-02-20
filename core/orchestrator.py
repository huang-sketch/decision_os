"""
多 Agent 编排器：统一入口 run_decision()。
编排顺序：idea_validator -> market_analyzer -> strategy_advisor -> reflector。
汇总为 DecisionReport，包含分阶段输出、反思、决策指数、用量。
不修改 engine/context/schemas 的语义。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .context import DecisionContext
from .engine import Engine


@dataclass
class DecisionReport:
    """决策引擎统一输出。"""

    # 底层上下文（保留完整 ctx 以兼容现有序列化/历史会话）
    ctx: DecisionContext

    # 决策指数
    decision_score: int = 0
    grade: str = "-"
    recommendation: str = "暂缓"
    risk_display: str = "中"
    scores: dict[str, int] = field(default_factory=dict)
    key_uncertainties: list[str] = field(default_factory=list)
    next_validation_checklist: list[str] = field(default_factory=list)

    # 用量
    usage: dict[str, Any] = field(default_factory=dict)

    # 运行耗时（秒）
    elapsed_time: float = 0.0


def run_decision(
    question: str,
    background: str = "",
    constraints: list[str] | None = None,
    llm_config: dict[str, Any] | None = None,
    calm_input: dict[str, Any] | None = None,
) -> DecisionReport:
    """
    一站式决策入口。

    参数:
        question: 用户问题
        background: 可选背景
        constraints: 可选约束列表
        llm_config: 可选 LLM 配置覆盖（预留，当前未使用）
        calm_input: 冷静度问卷原始输入（传给 evaluate_calm）

    返回:
        DecisionReport，包含 ctx、决策指数、用量、耗时。
    """
    from agents import (
        IdeaValidatorAgent,
        MarketAnalyzerAgent,
        StrategyAdvisorAgent,
        ReflectorAgent,
        evaluate_calm,
    )
    from app.usage import build_usage
    from app.decision_metrics import compute_metrics

    ctx = DecisionContext(
        user_input={
            "question": question.strip(),
            "background": (background or "").strip(),
            "constraints": list(constraints or []),
        }
    )

    registry = {
        "idea_validation": IdeaValidatorAgent(),
        "market_analysis": MarketAnalyzerAgent(),
        "strategy_advice": StrategyAdvisorAgent(),
    }
    reflector = ReflectorAgent()
    engine = Engine(agent_registry=registry, reflector=reflector)

    start = time.time()
    ctx = engine.run(ctx)
    elapsed = time.time() - start

    calm_data = evaluate_calm(calm_input)
    calm_data["_raw"] = calm_input or {}
    ctx.extra["calm"] = calm_data

    usage = build_usage(ctx)
    ctx.extra["usage"] = usage

    metrics = compute_metrics(ctx, calm_data=calm_data)

    return DecisionReport(
        ctx=ctx,
        decision_score=metrics.get("decision_score", 0),
        grade=metrics.get("grade", "-"),
        recommendation=metrics.get("recommendation", "暂缓"),
        risk_display=metrics.get("risk_display", "中"),
        scores=metrics.get("scores", {}),
        key_uncertainties=metrics.get("key_uncertainties", []),
        next_validation_checklist=metrics.get("next_validation_checklist", []),
        usage=usage,
        elapsed_time=elapsed,
    )


def run_decision_space_expand(
    question: str,
    background: str = "",
    context_dict: dict[str, Any] | None = None,
    constraints: list[str] | None = None,
    llm_config: dict[str, Any] | None = None,
    calm_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    扩展决策空间：自动生成保守/当前/激进三方案，各自调用 run_decision()，
    最后基于规则输出推荐方案与置信度。

    返回:
        {
            "baseline":  DecisionReport,
            "current":   DecisionReport,
            "aggressive": DecisionReport,
            "variants_meta": {key: variant_meta_dict, ...},
            "recommendation": {recommended_key, confidence, why, key_uncertainties},
            "elapsed_time": float,
        }
    """
    from .variants import generate_variants_rule_based, compute_recommendation

    variants = generate_variants_rule_based(
        question=question,
        background=background,
        context_dict=context_dict or {},
    )

    results: dict[str, DecisionReport] = {}
    start = time.time()

    for key in ("baseline", "current", "aggressive"):
        v = variants[key]
        bg = background + v["background_append"]
        results[key] = run_decision(
            question=v["question"],
            background=bg,
            constraints=constraints,
            llm_config=llm_config,
            calm_input=calm_input,
        )

    total_elapsed = time.time() - start

    triple_metrics = {}
    for key, report in results.items():
        triple_metrics[key] = {
            "decision_score": report.decision_score,
            "grade": report.grade,
            "recommendation": report.recommendation,
            "risk_display": report.risk_display,
            "scores": report.scores,
            "key_uncertainties": report.key_uncertainties,
        }

    rec = compute_recommendation(triple_metrics)

    return {
        "baseline": results["baseline"],
        "current": results["current"],
        "aggressive": results["aggressive"],
        "variants_meta": {k: v["variant_meta"] for k, v in variants.items()},
        "recommendation": rec,
        "elapsed_time": total_elapsed,
    }
