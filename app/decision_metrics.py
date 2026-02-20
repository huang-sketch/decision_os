"""
决策指数（Decision Metrics）v0.3。
基于 stages/reflection 的规则映射，可解释、可复现，不依赖 LLM。
缺字段时优雅降级，不报错。
"""
from __future__ import annotations

from typing import Any


def _get_stage(ctx: Any, stage_id: str) -> dict | None:
    stages = getattr(ctx, "stages", None) or {}
    return stages.get(stage_id)


def _feasibility_score(ctx: Any) -> tuple[int, list[str]]:
    """可行性 0-25，来自 idea_validation。"""
    issues = []
    stage = _get_stage(ctx, "idea_validation")
    if not stage:
        return 12, ["缺失 idea_validation，使用默认中等分"]
    valid = stage.get("valid", True)
    clarity = stage.get("clarity_score")
    if clarity is None:
        try:
            clarity = int(stage.get("clarity_score", 5))
        except (TypeError, ValueError):
            clarity = 5
    if not isinstance(clarity, int):
        clarity = 5
        issues.append("clarity_score 非整数，按 5 处理")
    clarity = max(1, min(10, clarity))
    if not valid:
        return 5, ["创意验证未通过，可行性偏低"]
    # valid=True: 5-10 -> 8~25
    score = 5 + clarity * 2  # 7->19, 10->25
    return min(25, max(0, score)), issues


def _market_score(ctx: Any) -> tuple[int, list[str]]:
    """市场 0-25，来自 market_analysis。"""
    issues = []
    stage = _get_stage(ctx, "market_analysis")
    if not stage:
        return 12, ["缺失 market_analysis，使用默认中等分"]
    trend = (stage.get("trend") or "").strip()
    competition = (stage.get("competition_level") or "").strip()
    size = (stage.get("market_size_estimate") or "").strip()
    # 规则：上升+低竞争+大=高；下降+高竞争=低
    score = 12
    if "上升" in trend:
        score += 5
    elif "下降" in trend:
        score -= 5
    if "低" in competition:
        score += 4
    elif "高" in competition:
        score -= 4
    if "大" in size:
        score += 2
    elif "小" in size:
        score -= 2
    return min(25, max(0, score)), issues


def _risk_score(ctx: Any) -> tuple[int, list[str]]:
    """风险维度 0-25：整体风险越低分数越高。"""
    issues = []
    stage = _get_stage(ctx, "strategy_advice")
    if not stage:
        return 12, ["缺失 strategy_advice，使用默认中等分"]
    level = (stage.get("overall_risk_level") or "").strip()
    if "低" in level:
        return 22, issues
    if "高" in level:
        return 6, issues
    return 14, issues  # 中


def _resource_score(ctx: Any) -> tuple[int, list[str]]:
    """资源 0-25，来自 strategy_advice 的 time/budget/gaps。"""
    issues = []
    stage = _get_stage(ctx, "strategy_advice")
    if not stage:
        return 12, ["缺失 strategy_advice，使用默认中等分"]
    gaps = stage.get("gaps") or []
    time_est = (stage.get("time_estimate") or "").strip()
    budget_est = (stage.get("budget_estimate") or "").strip()
    score = 14
    if isinstance(gaps, list) and len(gaps) == 0 and (time_est or budget_est):
        score = 20
    elif isinstance(gaps, list) and len(gaps) > 2:
        score = 8
    elif time_est or budget_est:
        score = 16
    return min(25, max(0, score)), issues


def _grade(decision_score: int) -> str:
    if decision_score >= 80:
        return "A"
    if decision_score >= 60:
        return "B"
    if decision_score >= 40:
        return "C"
    return "D"


def _recommendation(ctx: Any) -> str:
    stage = _get_stage(ctx, "strategy_advice")
    if not stage:
        return "暂缓"
    v = (stage.get("verdict") or "").strip()
    if "建议做" in v or "做" == v:
        return "做"
    if "谨慎" in v:
        return "谨慎"
    if "不建议" in v:
        return "不建议"
    if "暂缓" in v:
        return "暂缓"
    return v or "暂缓"


def _risk_display(ctx: Any) -> str:
    stage = _get_stage(ctx, "strategy_advice")
    if not stage:
        return "中"
    level = (stage.get("overall_risk_level") or "").strip()
    if "低" in level:
        return "低"
    if "高" in level:
        return "高"
    return "中"


def _key_uncertainties(ctx: Any) -> list[str]:
    out = []
    idea = _get_stage(ctx, "idea_validation")
    if idea:
        missing = idea.get("missing_info") or []
        if isinstance(missing, list):
            for m in missing[:3]:
                if m:
                    out.append(str(m))
    strategy = _get_stage(ctx, "strategy_advice")
    if strategy:
        gaps = strategy.get("gaps") or []
        if isinstance(gaps, list):
            for g in gaps[:3]:
                if g:
                    out.append(str(g))
    if not out:
        out.append("（暂无明确不确定性）")
    return out


def _next_validation_checklist(ctx: Any) -> list[str]:
    out = []
    strategy = _get_stage(ctx, "strategy_advice")
    if strategy:
        items = strategy.get("action_items") or []
        if isinstance(items, list):
            for it in items[:5]:
                if isinstance(it, dict) and it.get("action"):
                    out.append(it.get("action", ""))
                elif isinstance(it, str):
                    out.append(it)
    ref = getattr(ctx, "reflection", None) or {}
    actions = ref.get("suggested_actions") or []
    for a in actions[:3]:
        if a and a not in out:
            out.append(a)
    if not out:
        out.append("补充信息后重新跑一轮决策")
    return out


_CALM_WEIGHT = 0.15


def compute_metrics(ctx: Any, calm_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    计算决策指数并写入 ctx.extra["decision_metrics"]。

    Parameters
    ----------
    ctx : DecisionContext
    calm_data : dict, optional
        evaluate_calm() 的返回值。提供时会混合 calm_score 到最终指数，
        并根据 calm_level 修正 action_mode。
    """
    from agents.calm_evaluator import apply_calm_to_recommendation

    f_score, f_issues = _feasibility_score(ctx)
    m_score, m_issues = _market_score(ctx)
    r_score, r_issues = _risk_score(ctx)
    res_score, res_issues = _resource_score(ctx)

    base_score = f_score + m_score + r_score + res_score
    base_score = min(100, max(0, base_score))

    calm = calm_data or {}
    calm_score = calm.get("calm_score", 100)
    calm_level = calm.get("calm_level", "high")

    decision_score = round(base_score * (1 - _CALM_WEIGHT) + calm_score * _CALM_WEIGHT)
    decision_score = min(100, max(0, decision_score))

    raw_rec = _recommendation(ctx)
    action_mode = apply_calm_to_recommendation(raw_rec, calm_level)

    metrics = {
        "decision_score": decision_score,
        "base_score": base_score,
        "scores": {
            "feasibility": f_score,
            "market": m_score,
            "risk": r_score,
            "resource": res_score,
        },
        "grade": _grade(decision_score),
        "recommendation": action_mode,
        "risk_display": _risk_display(ctx),
        "key_uncertainties": _key_uncertainties(ctx),
        "next_validation_checklist": _next_validation_checklist(ctx),
        "missing_or_fallback": f_issues + m_issues + r_issues + res_issues,
        "calm_score": calm_score,
        "calm_level": calm_level,
        "cooldown_tip": calm.get("cooldown_tip", ""),
        "action_mode": action_mode,
    }
    extra = getattr(ctx, "extra", None)
    if extra is not None:
        extra["decision_metrics"] = metrics
    return metrics


# ---------------------------------------------------------------------------
# 可视化（matplotlib，供 Streamlit st.pyplot 使用）
# ---------------------------------------------------------------------------

_DIMENSION_LABELS = {
    "feasibility": "可行性",
    "market": "市场",
    "risk": "风险",
    "resource": "资源",
}
_DIMENSION_ORDER = ["feasibility", "market", "risk", "resource"]

# 模块级初始化 matplotlib（仅一次，避免在函数内反复 use("Agg")）
_MPL_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    _MPL_AVAILABLE = True
except Exception:
    plt = None  # type: ignore[assignment]
    np = None   # type: ignore[assignment]


def extract_subscores(metrics: dict[str, Any] | None) -> dict[str, int] | None:
    """
    从 metrics 中健壮地提取分项 scores dict。
    兼容路径：metrics["scores"] / metrics["subscores"] / metrics 本身含 4 个 key。
    返回 {"feasibility": int, "market": int, "risk": int, "resource": int} 或 None。
    """
    if not metrics or not isinstance(metrics, dict):
        return None

    # 优先 metrics["scores"]，其次 metrics["subscores"]
    raw = metrics.get("scores") or metrics.get("subscores")
    if not raw or not isinstance(raw, dict):
        # 兜底：看 metrics 本身是否直接含 4 个维度 key
        if all(k in metrics for k in _DIMENSION_ORDER):
            raw = metrics
        else:
            return None

    result: dict[str, int] = {}
    for k in _DIMENSION_ORDER:
        v = raw.get(k)
        if v is None:
            return None
        try:
            result[k] = int(v)
        except (TypeError, ValueError):
            return None
    return result


def build_radar_chart(scores: dict[str, int]) -> "Figure | None":
    """分项雷达图（各维度 0-25）。"""
    if not _MPL_AVAILABLE or not scores:
        return None

    labels = [_DIMENSION_LABELS.get(k, k) for k in _DIMENSION_ORDER]
    values = [scores.get(k, 0) for k in _DIMENSION_ORDER]

    num = len(labels)
    angles = np.linspace(0, 2 * np.pi, num, endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    ax.plot(angles_closed, values_closed, "o-", linewidth=2, color="#4C72B0")
    ax.fill(angles_closed, values_closed, alpha=0.25, color="#4C72B0")
    ax.set_thetagrids(np.degrees(angles), labels, fontsize=11)
    ax.set_rlim(0, 25)
    ax.set_rticks([5, 10, 15, 20, 25])
    ax.set_title("分项评分雷达图", fontsize=13, pad=18)
    fig.tight_layout()
    return fig


def build_bar_chart(scores: dict[str, int], decision_score: int = 0) -> "Figure | None":
    """分项柱状图 + 综合分标注。"""
    if not _MPL_AVAILABLE or not scores:
        return None

    labels = [_DIMENSION_LABELS.get(k, k) for k in _DIMENSION_ORDER]
    values = [scores.get(k, 0) for k in _DIMENSION_ORDER]
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(labels, values, color=colors, width=0.55, edgecolor="white")
    ax.set_ylim(0, 28)
    ax.set_ylabel("得分（满分25）", fontsize=10)
    ax.set_title(f"分项评分  |  综合分: {decision_score}/100", fontsize=12)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.6, str(val),
                ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 三方案对比可视化
# ---------------------------------------------------------------------------

_VARIANT_COLORS: dict[str, tuple[str, str]] = {
    "baseline": ("#2196F3", "保守"),
    "current": ("#4CAF50", "当前"),
    "aggressive": ("#FF5722", "激进"),
}
_VARIANT_ORDER = ("baseline", "current", "aggressive")


def build_triple_radar_chart(
    triple_scores: dict[str, dict[str, int]],
) -> "Figure | None":
    """三方案叠加雷达图（各维度 0-25）。"""
    if not _MPL_AVAILABLE or not triple_scores:
        return None

    labels = [_DIMENSION_LABELS.get(k, k) for k in _DIMENSION_ORDER]
    num = len(labels)
    angles = np.linspace(0, 2 * np.pi, num, endpoint=False).tolist()
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))

    for key in _VARIANT_ORDER:
        scores = triple_scores.get(key)
        if not scores:
            continue
        color, label = _VARIANT_COLORS[key]
        values = [scores.get(k, 0) for k in _DIMENSION_ORDER]
        values_closed = values + [values[0]]
        ax.plot(angles_closed, values_closed, "o-", linewidth=2, color=color, label=label)
        ax.fill(angles_closed, values_closed, alpha=0.08, color=color)

    ax.set_thetagrids(np.degrees(angles), labels, fontsize=11)
    ax.set_rlim(0, 25)
    ax.set_rticks([5, 10, 15, 20, 25])
    ax.set_title("三方案分项对比", fontsize=13, pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.12), fontsize=10)
    fig.tight_layout()
    return fig


def build_triple_bar_chart(
    triple_totals: dict[str, int],
) -> "Figure | None":
    """三方案综合分柱状图。"""
    if not _MPL_AVAILABLE or not triple_totals:
        return None

    keys = list(_VARIANT_ORDER)
    labels = [_VARIANT_COLORS[k][1] for k in keys]
    values = [triple_totals.get(k, 0) for k in keys]
    colors = [_VARIANT_COLORS[k][0] for k in keys]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")
    ax.set_ylim(0, 110)
    ax.set_ylabel("综合分（满分 100）", fontsize=10)
    ax.set_title("三方案综合分对比", fontsize=12)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, val + 1.5, str(val),
            ha="center", va="bottom", fontsize=12, fontweight="bold",
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 低碳诊断可视化
# ---------------------------------------------------------------------------

_LC_DIMS = ["运距", "土石方", "预制率", "电动化", "工期压力", "固废利用"]


def build_lowcarbon_bar_chart(
    current_idx: float, target_idx: float, conservative_idx: float,
) -> "Figure | None":
    """三情景低碳诊断指数对比。"""
    if not _MPL_AVAILABLE:
        return None
    labels = ["当前方案", "低碳优化", "保守落地"]
    values = [current_idx, target_idx, conservative_idx]
    colors = ["#E64A19", "#4CAF50", "#1976D2"]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white")
    ax.set_ylim(0, 115)
    ax.set_ylabel("低碳诊断指数", fontsize=10)
    ax.set_title("情景对比", fontsize=12)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1.5,
                f"{val:.1f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def build_lowcarbon_radar_chart(
    current_radar: dict, target_radar: dict,
) -> "Figure | None":
    """当前方案 vs 优化目标 雷达图叠加（各维度 0-10）。"""
    if not _MPL_AVAILABLE:
        return None
    if not current_radar and not target_radar:
        return None

    num = len(_LC_DIMS)
    angles = np.linspace(0, 2 * np.pi, num, endpoint=False).tolist()
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    for radar, color, label in [
        (current_radar, "#E64A19", "当前方案"),
        (target_radar, "#4CAF50", "优化目标"),
    ]:
        if not radar:
            continue
        vals = [radar.get(d, 0) for d in _LC_DIMS]
        vals_closed = vals + [vals[0]]
        ax.plot(angles_closed, vals_closed, "o-", linewidth=2, color=color, label=label)
        ax.fill(angles_closed, vals_closed, alpha=0.08, color=color)

    ax.set_thetagrids(np.degrees(angles), _LC_DIMS, fontsize=10)
    ax.set_rlim(0, 10)
    ax.set_rticks([2, 4, 6, 8, 10])
    ax.set_title("低碳因子诊断（越外越优）", fontsize=12, pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.12), fontsize=10)
    fig.tight_layout()
    return fig
