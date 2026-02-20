"""
扩展决策空间：基于规则在固定维度上生成保守 / 当前 / 激进三方案变体。
仅用于创业场景，不引入额外依赖。
"""
from __future__ import annotations

from typing import Any

_DEADLINE_SCALE: dict[str, tuple[str, str]] = {
    "1 个月": ("2 个月", "2 周"),
    "3 个月": ("6 个月", "1.5 个月"),
    "6 个月": ("1 年", "3 个月"),
    "1 年": ("1.5 年", "6 个月"),
}


def generate_variants_rule_based(
    question: str,
    background: str,
    context_dict: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    在 7 个固定维度上对用户方案做保守 / 激进调档，返回三个变体描述。

    background_append 会追加到用户原 background 末尾，不覆盖原文。
    variant_meta 记录每个维度的具体设定，供 UI 展示。
    """
    deadline = context_dict.get("deadline", "3 个月")
    bl_deadline, ag_deadline = _DEADLINE_SCALE.get(deadline, ("6 个月", "1.5 个月"))

    constraint_text = context_dict.get("constraint", "").strip()
    success_text = context_dict.get("success_criteria", "").strip()

    # 从约束中取第一条作为激进方案可突破项
    breakable = ""
    if constraint_text:
        first = constraint_text.replace("，", ",").split(",")[0].strip()
        if first:
            breakable = f"允许突破约束「{first}」（仅此一项，其余仍遵守）"

    # ── Baseline（保守） ──
    bl_meta = {
        "time_commitment": "仅利用业余时间，不影响主业收入",
        "budget": "零额外投入或极低投入（<500 元/月）",
        "validation_window": bl_deadline,
        "output_frequency": "低频产出，每周 1-2 次迭代",
        "risk_exposure": "不辞职、不投流、不借钱、不动用应急储蓄",
        "success_metric": (
            f"降低预期：{success_text} 的 50%" if success_text
            else "验证基本可行性即可"
        ),
        "constraint_compliance": "严格满足所有约束条件",
    }
    bl_append = (
        "\n\n【执行策略 — 保守方案】\n"
        + "\n".join(f"- {v}" for v in bl_meta.values())
    )

    # ── Aggressive（激进） ──
    ag_meta = {
        "time_commitment": "全力投入，可减少主业时间或考虑阶段性全职",
        "budget": "增加预算至可承受上限，允许适度投入推广",
        "validation_window": ag_deadline,
        "output_frequency": "高频产出，每日迭代，快速试错",
        "risk_exposure": "可考虑投流获客、适度杠杆，但不超过总资产 20%",
        "success_metric": (
            f"提高预期：{success_text} 的 150%" if success_text
            else "追求超额验证和规模化信号"
        ),
        "constraint_compliance": breakable or "在可控范围内适度放宽约束",
    }
    ag_append = (
        "\n\n【执行策略 — 激进方案】\n"
        + "\n".join(f"- {v}" for v in ag_meta.values())
    )

    # ── Current（当前） ──
    cur_meta = {
        "time_commitment": "按用户原始计划",
        "budget": "按用户原始计划",
        "validation_window": deadline,
        "output_frequency": "按用户原始计划",
        "risk_exposure": "按用户原始计划",
        "success_metric": success_text or "按用户原始计划",
        "constraint_compliance": "按用户设定的约束执行",
    }

    return {
        "baseline": {
            "title": "保守方案 (Baseline)",
            "question": question,
            "background_append": bl_append,
            "variant_meta": bl_meta,
        },
        "current": {
            "title": "当前方案 (Current)",
            "question": question,
            "background_append": "",
            "variant_meta": cur_meta,
        },
        "aggressive": {
            "title": "激进方案 (Aggressive)",
            "question": question,
            "background_append": ag_append,
            "variant_meta": ag_meta,
        },
    }


def compute_recommendation(triple_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    基于三方案指标对比输出推荐 + 置信度。

    推荐逻辑：综合分优先 → 高风险惩罚 → 分差小则降低置信度。
    """
    _NAMES = {"baseline": "保守方案", "current": "当前方案", "aggressive": "激进方案"}

    adjusted: dict[str, float] = {}
    for key in ("baseline", "current", "aggressive"):
        m = triple_metrics.get(key, {})
        raw = m.get("decision_score", 0)
        risk = m.get("risk_display", "中")
        penalty = 8 if "高" in risk else (-3 if "低" in risk else 0)
        adjusted[key] = raw - penalty

    ranked = sorted(adjusted, key=lambda k: adjusted[k], reverse=True)
    best = ranked[0]

    spread = max(adjusted.values()) - min(adjusted.values())
    if spread >= 20:
        confidence = 0.85
    elif spread >= 10:
        confidence = 0.65
    elif spread >= 5:
        confidence = 0.45
    else:
        confidence = 0.25

    best_m = triple_metrics.get(best, {})
    best_raw = best_m.get("decision_score", 0)
    best_risk = best_m.get("risk_display", "中")
    best_grade = best_m.get("grade", "-")

    why: list[str] = [
        f"{_NAMES[best]}综合分最高（{best_raw}/100，等级 {best_grade}）",
    ]
    if "高" not in best_risk:
        why.append(f"风险水平「{best_risk}」，在可控范围内")
    else:
        why.append("虽然风险较高，但综合收益显著领先")

    second = ranked[1]
    gap = best_raw - triple_metrics.get(second, {}).get("decision_score", 0)
    if gap > 0:
        why.append(f"领先{_NAMES[second]} {gap} 分")
    else:
        why.append(f"与{_NAMES[second]}分差极小，建议结合个人偏好判断")

    uncertainties: list[str] = []
    if spread < 10:
        uncertainties.append("三方案分差较小，推荐置信度有限，建议结合自身风险偏好判断")
    for key in ("baseline", "current", "aggressive"):
        for u in triple_metrics.get(key, {}).get("key_uncertainties", [])[:1]:
            if u and u not in uncertainties:
                uncertainties.append(f"[{_NAMES[key]}] {u}")
    if not uncertainties:
        uncertainties.append("各方案均存在市场验证不确定性，建议小步验证")

    return {
        "recommended_key": best,
        "confidence": round(confidence, 2),
        "why": why[:3],
        "key_uncertainties": uncertainties[:3],
    }
