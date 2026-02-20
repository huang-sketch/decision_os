"""
设计前期低碳诊断与优化建模。
参数化估算，用于方案讨论与优化方向识别，不替代正式评价/核算结论。
"""
from __future__ import annotations

from typing import Any

# ── 基线参数 ──

_K_MAP = {4: 1.0, 6: 1.31, 8: 1.65}

_LEVEL_DELTAS: dict[str, dict[str, float]] = {
    "earthwork":         {"低": 0.00, "中": 0.05, "高": 0.10},
    "prefab_rate":       {"低": 0.00, "中": -0.05, "高": -0.10},
    "electrification":   {"低": 0.00, "中": -0.04, "高": -0.08},
    "schedule_pressure": {"低": 0.00, "中": 0.03,  "高": 0.08},
    "waste_recycling":   {"低": 0.00, "中": -0.03, "高": -0.06},
}

_LEVEL_ORDER = ["低", "中", "高"]

_FACTOR_CEIL = {
    "运距": 0.15, "土石方": 0.10, "预制率": 0.10,
    "电动化": 0.08, "工期压力": 0.08, "固废利用": 0.06,
}
_FACTOR_HIGHER_IS_WORSE = {
    "运距": True, "土石方": True, "预制率": False,
    "电动化": False, "工期压力": True, "固废利用": False,
}
RADAR_DIMS = list(_FACTOR_CEIL.keys())

_IMPROVEMENT_RULES: dict[str, tuple[str, str]] = {
    "土石方":  ("earthwork", "decrease"),
    "预制率":  ("prefab_rate", "increase"),
    "电动化":  ("electrification", "increase"),
    "工期压力": ("schedule_pressure", "decrease"),
    "固废利用": ("waste_recycling", "increase"),
}

_LOW_RISK_LABELS = {"预制率", "固废利用", "电动化"}

_PREREQUISITES = {
    "运距":   "需确认材料供应商及运输路线方案",
    "土石方": "需完成初步土石方调配方案",
    "预制率": "需确认预制构件供应能力与运输条件",
    "电动化": "需评估施工现场电力接入条件",
    "工期压力": "需与建设单位确认工期弹性空间",
    "固废利用": "需确认固废处置场地及资源化利用渠道",
}


# ── 基线与修正 ──

def compute_ye(xe_pct: float, lanes: int) -> float:
    """基准碳排放强度 Ye (tCO₂e/km)。"""
    k = _K_MAP.get(lanes, 1.0)
    return 721.3 * xe_pct * k


def _transport_delta(distance_km: float) -> float:
    if distance_km < 30:
        return 0.0
    if distance_km < 60:
        return 0.05
    if distance_km < 100:
        return 0.10
    return 0.15


def compute_delta(factors: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """增强修正层 → (总Δ, 各因子贡献)。"""
    bd: dict[str, float] = {}
    bd["运距"] = _transport_delta(factors.get("transport_distance", 0))
    for key, label in [
        ("earthwork", "土石方"), ("prefab_rate", "预制率"),
        ("electrification", "电动化"), ("schedule_pressure", "工期压力"),
        ("waste_recycling", "固废利用"),
    ]:
        bd[label] = _LEVEL_DELTAS[key].get(factors.get(key, "低"), 0.0)
    return sum(bd.values()), bd


def _compute_index(e_val: float, ye: float) -> float:
    """低碳诊断指数 0-100（越高越低碳）。"""
    if ye <= 0:
        return 0.0
    raw = 20.0 if e_val <= ye else (ye / e_val) * 20.0
    return round(raw / 20 * 100, 1)


def compute_risk(env: str, geo: str, schedule: str) -> str:
    high = sum(1 for f in (env, geo, schedule) if f == "高")
    if high >= 2:
        return "高"
    mid = sum(1 for f in (env, geo, schedule) if f == "中")
    if high == 1 or mid >= 2:
        return "中"
    return "低"


def _to_radar(bd: dict[str, float]) -> dict[str, float]:
    """因子贡献 → 0-10 雷达分（越高越低碳）。"""
    out: dict[str, float] = {}
    for dim in RADAR_DIMS:
        val = bd.get(dim, 0.0)
        ceil = _FACTOR_CEIL[dim]
        if _FACTOR_HIGHER_IS_WORSE[dim]:
            out[dim] = max(0.0, min(10.0, 10 * (1 - abs(val) / ceil)))
        else:
            out[dim] = max(0.0, min(10.0, 10 * abs(val) / ceil))
    return {k: round(v, 2) for k, v in out.items()}


# ── 情景生成 ──

def _collect_candidates(
    scheme: dict[str, Any], breakdown: dict[str, float],
) -> list[tuple[str, float, str, bool]]:
    """收集所有可改善一档的候选项，返回 (label, improvement, action, is_low_risk)。"""
    candidates: list[tuple[str, float, str, bool]] = []

    td = scheme.get("transport_distance", 0)
    td_cur = breakdown.get("运距", 0)
    if td >= 100:
        candidates.append(("运距", td_cur - _transport_delta(80),
                           "缩短平均运距至 60-100 km", False))
    elif td >= 60:
        candidates.append(("运距", td_cur - _transport_delta(45),
                           "缩短平均运距至 30-60 km", False))
    elif td >= 30:
        candidates.append(("运距", td_cur - _transport_delta(15),
                           "缩短平均运距至 30 km 以内", False))

    for label, (input_key, direction) in _IMPROVEMENT_RULES.items():
        cur_level = scheme.get(input_key, "低")
        cur_d = breakdown.get(label, 0)
        idx = _LEVEL_ORDER.index(cur_level) if cur_level in _LEVEL_ORDER else 1
        is_low_risk = label in _LOW_RISK_LABELS
        if direction == "decrease" and idx > 0:
            new_lv = _LEVEL_ORDER[idx - 1]
            new_d = _LEVEL_DELTAS[input_key][new_lv]
            candidates.append((label, cur_d - new_d,
                               f"{label}从「{cur_level}」降至「{new_lv}」", is_low_risk))
        elif direction == "increase" and idx < 2:
            new_lv = _LEVEL_ORDER[idx + 1]
            new_d = _LEVEL_DELTAS[input_key][new_lv]
            candidates.append((label, cur_d - new_d,
                               f"{label}从「{cur_level}」提至「{new_lv}」", is_low_risk))

    return [(l, imp, a, lr) for l, imp, a, lr in candidates if abs(imp) > 1e-6]


def _apply_improvements(
    breakdown: dict[str, float],
    selected: list[tuple[str, float, str, bool]],
    total_delta: float,
    ye: float,
) -> tuple[float, dict[str, float], float, list[dict[str, Any]]]:
    improved_bd = dict(breakdown)
    optimizations: list[dict[str, Any]] = []
    for label, improvement, action, *_ in selected:
        improved_bd[label] = round(breakdown[label] - improvement, 4)
        denom = (1 + total_delta) if (1 + total_delta) else 1
        est_pct = abs(improvement) / denom * 100
        optimizations.append({
            "action": action,
            "delta_change": round(-improvement, 4),
            "estimated_reduction_pct": round(est_pct, 1),
        })
    new_delta = round(sum(improved_bd.values()), 4)
    e_val = ye * (1 + new_delta)
    return new_delta, improved_bd, e_val, optimizations


def _generate_target(
    scheme: dict[str, Any], ye: float,
    breakdown: dict[str, float], total_delta: float,
) -> tuple[float, dict[str, float], float, list[dict[str, Any]]]:
    """Target（低碳优化）：选择贡献最大的 2-3 个杠杆各改善一档。"""
    candidates = _collect_candidates(scheme, breakdown)
    candidates.sort(key=lambda x: abs(x[1]), reverse=True)
    return _apply_improvements(breakdown, candidates[:3], total_delta, ye)


def _generate_conservative(
    scheme: dict[str, Any], ye: float,
    breakdown: dict[str, float], total_delta: float,
) -> tuple[float, dict[str, float], float, list[dict[str, Any]]]:
    """Conservative（保守落地）：优先低风险、高可落地性的 1-2 项改善。"""
    candidates = _collect_candidates(scheme, breakdown)
    low_risk = sorted([c for c in candidates if c[3]],
                      key=lambda x: abs(x[1]), reverse=True)
    high_risk = sorted([c for c in candidates if not c[3]],
                       key=lambda x: abs(x[1]), reverse=True)
    selected = low_risk[:2]
    if not selected and high_risk:
        selected = high_risk[:1]
    return _apply_improvements(breakdown, selected, total_delta, ye)


# ── 生态影响 ──

_LAND_SCALE_BASE = {"小": 90, "中": 65, "大": 40}
_LAND_SENSITIVITY_MULT = {"低": 1.0, "中": 0.8, "高": 0.6}


def compute_ecology_index(
    land_scale: str = "中",
    land_sensitivity: str = "中",
    involves_forest_water: bool = False,
) -> dict[str, Any]:
    base = _LAND_SCALE_BASE.get(land_scale, 65)
    mult = _LAND_SENSITIVITY_MULT.get(land_sensitivity, 0.8)
    idx = base * mult
    if involves_forest_water:
        idx *= 0.7
    idx = max(0, min(100, round(idx, 1)))

    risk = "低" if idx >= 70 else ("中" if idx >= 40 else "高")

    suggestions: list[str] = []
    if land_scale in ("中", "大"):
        suggestions.append("优化线位方案，减少永久占地面积与取弃土场规模")
    if land_sensitivity in ("中", "高"):
        suggestions.append("线位避让高生态敏感区域，或增设生态防护与恢复措施")
    if involves_forest_water:
        suggestions.append(
            "论证林地/水域替代方案，优化互通与服务区选址以减少占用")
    if not suggestions:
        suggestions.append("当前生态影响可控，建议保持现有线位方案并关注施工期防护")

    return {"index": idx, "risk": risk, "suggestions": suggestions[:3]}


# ── 碳汇潜力 ──

_SINK_SCORES = {"常规": 35, "增强": 60, "示范": 85}


def compute_carbon_sink_index(greening_intensity: str = "常规") -> dict[str, Any]:
    idx = _SINK_SCORES.get(greening_intensity, 35)
    suggestions: list[str] = []
    if greening_intensity == "常规":
        suggestions.append("考虑增设高固碳植被带（乔灌草复层结构），提升碳汇能力")
        suggestions.append("在边坡防护中引入生态化设计，兼顾固碳与水土保持")
    elif greening_intensity == "增强":
        suggestions.append("规划绿化廊道连接沿线生态斑块，提升碳汇连续性")
        suggestions.append("优选固碳效率高的乡土树种，提升长期碳汇效益")
    else:
        suggestions.append("保持示范级绿化标准，可作为项目碳中和贡献亮点")
    return {"index": idx, "suggestions": suggestions[:2]}


# ── 主入口 ──

def run_lowcarbon_diagnosis(scheme: dict[str, Any]) -> dict[str, Any]:
    """单方案低碳诊断 + 自动三情景生成 + 生态/碳汇模块。"""
    ye = compute_ye(scheme.get("xe_pct", 0), scheme.get("lanes", 4))
    factors = {k: scheme.get(k) for k in
               ("transport_distance", "earthwork", "prefab_rate",
                "electrification", "schedule_pressure", "waste_recycling")}
    delta, bd = compute_delta(factors)
    e_est = ye * (1 + delta)
    lc_index = _compute_index(e_est, ye)

    risk = compute_risk(
        scheme.get("env_sensitive", "低"),
        scheme.get("geo_complexity", "低"),
        scheme.get("schedule_pressure", "低"),
    )

    # Target scenario
    tgt_delta, tgt_bd, e_target, tgt_opts = _generate_target(
        scheme, ye, bd, delta)
    tgt_index = _compute_index(e_target, ye)
    tgt_improve = (e_est - e_target) / e_est * 100 if e_est > 0 else 0

    # Conservative scenario
    con_delta, con_bd, e_con, con_opts = _generate_conservative(
        scheme, ye, bd, delta)
    con_index = _compute_index(e_con, ye)
    con_improve = (e_est - e_con) / e_est * 100 if e_est > 0 else 0

    # Levers
    total_abs = sum(abs(v) for v in bd.values()) or 1
    levers = sorted(
        [{"factor": k, "delta": v,
          "contribution_pct": round(abs(v) / total_abs * 100, 1),
          "direction": "↑排放" if v > 0 else "↓减碳",
          "impact_range": f"{abs(v)*0.8:.1%} ~ {abs(v)*1.2:.1%}"}
         for k, v in bd.items() if abs(v) > 1e-6],
        key=lambda x: x["contribution_pct"], reverse=True,
    )[:3]

    # Design suggestions
    design_suggestions: list[dict[str, str]] = []
    for opt in tgt_opts[:3]:
        factor_key = next((k for k in _PREREQUISITES if k in opt["action"]), "")
        pct = opt["estimated_reduction_pct"]
        design_suggestions.append({
            "action": opt["action"],
            "estimated_range": f"{max(0.5, pct - 1):.1f}% ~ {pct + 1:.1f}%",
            "prerequisite": _PREREQUISITES.get(factor_key, "需进一步确认可行性"),
        })

    uncertainties = [
        "基准强度基于经验参数模型，精度随勘察深度提升",
        "修正因子来自档位化估算，实际值需施工方案确认",
        "优化目标为理论推演，实施可行性需结合项目条件论证",
    ]
    next_steps = [
        "补充材料清单与运输方案，细化运距数据",
        "确认桥隧结构方案，核实桥隧比",
        "获取预制构件供应商碳排放因子",
    ]
    if risk in ("中", "高"):
        next_steps.append("开展环境敏感区影响评估")
    next_steps.append("完善设计参数后复算更新")

    ecology = compute_ecology_index(
        scheme.get("land_scale", "中"),
        scheme.get("land_sensitivity", "中"),
        scheme.get("involves_forest_water", False),
    )
    carbon_sink = compute_carbon_sink_index(
        scheme.get("greening_intensity", "常规"),
    )

    return {
        "current": {
            "ye": round(ye, 1),
            "delta": round(delta, 4),
            "delta_breakdown": {k: round(v, 4) for k, v in bd.items()},
            "e_est": round(e_est, 1),
            "lowcarbon_index": lc_index,
            "risk_level": risk,
            "radar_scores": _to_radar(bd),
        },
        "target": {
            "delta": tgt_delta,
            "delta_breakdown": {k: round(v, 4) for k, v in tgt_bd.items()},
            "e_value": round(e_target, 1),
            "lowcarbon_index": tgt_index,
            "improvement_pct": round(tgt_improve, 1),
            "radar_scores": _to_radar(tgt_bd),
            "optimizations": tgt_opts,
        },
        "conservative": {
            "delta": con_delta,
            "delta_breakdown": {k: round(v, 4) for k, v in con_bd.items()},
            "e_value": round(e_con, 1),
            "lowcarbon_index": con_index,
            "improvement_pct": round(con_improve, 1),
            "radar_scores": _to_radar(con_bd),
            "optimizations": con_opts,
        },
        "levers": levers,
        "design_suggestions": design_suggestions,
        "key_uncertainties": uncertainties,
        "next_steps": next_steps[:5],
        "ecology": ecology,
        "carbon_sink": carbon_sink,
        "input_summary": {
            "road_grade": scheme.get("road_grade", "-"),
            "length_km": scheme.get("length_km", 0),
            "lanes": scheme.get("lanes", 4),
            "xe_pct": scheme.get("xe_pct", 0),
        },
    }
