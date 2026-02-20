"""
Streamlit 演示层（v0.2）。
从项目根目录运行: streamlit run app/web_app.py
支持 Mock / Qwen；每次运行后自动保存 session 到 data/sessions，并提供下载。
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# 保证项目根在 path 中（以 core/agents 可被 import）
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 立即加载 .env（必须在读取环境变量之前）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st

from core import DecisionContext, Engine, run_decision, run_decision_space_expand
from agents import (
    IdeaValidatorAgent,
    MarketAnalyzerAgent,
    StrategyAdvisorAgent,
    ReflectorAgent,
)
from app.usage import get_llm_status_display, build_usage
from app.decision_metrics import (
    compute_metrics, extract_subscores,
    build_radar_chart, build_bar_chart,
    build_triple_radar_chart, build_triple_bar_chart,
    build_lowcarbon_bar_chart, build_lowcarbon_radar_chart,
)

# 初始化 session_state
if "current_ctx" not in st.session_state:
    st.session_state.current_ctx = None
if "run_time" not in st.session_state:
    st.session_state.run_time = None
if "usage" not in st.session_state:
    st.session_state.usage = None
if "triple_result" not in st.session_state:
    st.session_state.triple_result = None
if "lowcarbon_result" not in st.session_state:
    st.session_state.lowcarbon_result = None


def get_qwen_model_display() -> str:
    """仅当 Qwen 已就绪时返回模型名，否则返回 '-'。"""
    if (os.getenv("LLM_PROVIDER") or "").strip().lower() == "qwen" and (os.getenv("DASHSCOPE_API_KEY") or "").strip():
        return (os.getenv("QWEN_MODEL") or "qwen-plus").strip()
    return "-"


def ctx_to_dict(ctx: DecisionContext) -> dict:
    """将 DecisionContext 序列化为可 JSON 的 dict（不修改 context 结构）。"""
    return asdict(ctx)


def _ensure_decision_metrics(ctx: DecisionContext) -> dict:
    """若 ctx.extra 中无 decision_metrics 则计算并写入。"""
    extra = getattr(ctx, "extra", None) or {}
    if "decision_metrics" in extra:
        return extra["decision_metrics"]
    return compute_metrics(ctx)


def render_kpi(metrics: dict | None) -> None:
    """顶部 KPI：综合分、等级、建议、风险 + 图表。"""
    if not metrics:
        return
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("综合分", f"{metrics.get('decision_score', 0)}/100")
    with col2:
        st.metric("等级", metrics.get("grade", "-"))
    with col3:
        st.metric("建议", metrics.get("recommendation", "-"))
    with col4:
        st.metric("风险", metrics.get("risk_display", "-"))

    scores = extract_subscores(metrics)
    if not scores:
        st.caption("暂无分项数据，无法生成图表")
        return

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        radar_fig = build_radar_chart(scores)
        if radar_fig:
            st.pyplot(radar_fig)
            import matplotlib.pyplot as _plt
            _plt.close(radar_fig)
        else:
            st.caption("雷达图不可用（matplotlib 未安装）")
    with chart_col2:
        bar_fig = build_bar_chart(scores, metrics.get("decision_score", 0))
        if bar_fig:
            st.pyplot(bar_fig)
            import matplotlib.pyplot as _plt
            _plt.close(bar_fig)
        else:
            st.caption("柱状图不可用（matplotlib 未安装）")


def generate_markdown_report(ctx: DecisionContext) -> str:
    """生成 Markdown 格式的决策报告（含 v0.3 决策指数）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    question = ctx.user_input.get("question", "")
    background = ctx.user_input.get("background", "")
    
    lines = [
        f"# AI 决策报告 - {now}",
        "",
        "## 用户输入",
        "",
        f"**问题：** {question}",
    ]
    
    if background:
        lines.append(f"**背景：** {background}")
    
    # 决策指数（v0.3）
    metrics = _ensure_decision_metrics(ctx)
    lines.extend([
        "",
        "## 决策指数（v0.3）",
        "",
        f"- **综合分：** {metrics.get('decision_score', 0)}/100",
        f"- **等级：** {metrics.get('grade', '-')}",
        f"- **建议：** {metrics.get('recommendation', '-')}",
        f"- **风险：** {metrics.get('risk_display', '-')}",
        "",
        "### 分项分",
        "",
    ])
    scores = metrics.get("scores") or {}
    for name, val in [("可行性 feasibility", scores.get("feasibility")), ("市场 market", scores.get("market")), ("风险 risk", scores.get("risk")), ("资源 resource", scores.get("resource"))]:
        lines.append(f"- {name}: {val}/25")
    lines.extend([
        "",
        "### 关键不确定性",
        "",
    ])
    for u in metrics.get("key_uncertainties") or []:
        lines.append(f"- {u}")
    lines.extend([
        "",
        "### 下一步验证清单",
        "",
    ])
    for v in metrics.get("next_validation_checklist") or []:
        lines.append(f"- {v}")
    lines.append("")

    # 核心判断
    strategy_md = ctx.get_stage("strategy_advice") or {}
    one_liner_md = strategy_md.get("one_liner", "")
    reasons_md = (strategy_md.get("reasons") or [])[:3]
    next_steps_md: list[str] = []
    if ctx.reflection:
        next_steps_md = list(ctx.reflection.get("suggested_actions") or [])[:3]
    if len(next_steps_md) < 3:
        for _ai in strategy_md.get("action_items") or []:
            if len(next_steps_md) >= 3:
                break
            _txt = _ai.get("action", "") if isinstance(_ai, dict) else str(_ai)
            if _txt and _txt not in next_steps_md:
                next_steps_md.append(_txt)

    lines.extend(["## 核心判断", ""])
    lines.append(f"**一句话结论：** {one_liner_md or '暂无'}")
    lines.append("")
    lines.append("**关键原因：**")
    for i, r in enumerate(reasons_md, 1):
        lines.append(f"{i}. {r}")
    if not reasons_md:
        lines.append("- 暂无")
    lines.append("")
    lines.append("**下一步建议：**")
    for i, ns in enumerate(next_steps_md, 1):
        lines.append(f"{i}. {ns}")
    if not next_steps_md:
        lines.append("- 暂无")
    lines.append("")

    lines.extend([
        "## 决策阶段",
        "",
        "### Stage 1：问题解析",
    ])
    
    idea_stage = ctx.get_stage("idea_validation")
    if idea_stage:
        lines.append(f"- **有效性：** {'是' if idea_stage.get('valid') else '否'}")
        lines.append(f"- **清晰度评分：** {idea_stage.get('clarity_score', 'N/A')}")
        lines.append(f"- **总结：** {idea_stage.get('summary', '')}")
        assumptions = idea_stage.get('assumptions', [])
        if assumptions:
            lines.append(f"- **假设：** {', '.join(assumptions)}")
        missing_info = idea_stage.get('missing_info', [])
        if missing_info:
            lines.append(f"- **缺失信息：** {', '.join(missing_info)}")
        lines.append("")
    
    lines.extend([
        "### Stage 2：市场分析",
    ])
    
    market_stage = ctx.get_stage("market_analysis")
    if market_stage:
        lines.append(f"- **市场规模：** {market_stage.get('market_size_estimate', 'N/A')}")
        lines.append(f"- **趋势：** {market_stage.get('trend', 'N/A')}")
        lines.append(f"- **竞争水平：** {market_stage.get('competition_level', 'N/A')}")
        competitors = market_stage.get('key_competitors', [])
        if competitors:
            lines.append(f"- **主要竞品：** {', '.join(competitors)}")
        lines.append(f"- **机会总结：** {market_stage.get('opportunity_summary', '')}")
        risks = market_stage.get('risks', [])
        if risks:
            lines.append(f"- **风险：** {', '.join(risks)}")
        lines.append("")
    
    lines.extend([
        "### Stage 3：策略建议",
    ])
    
    strategy_stage = ctx.get_stage("strategy_advice")
    if strategy_stage:
        lines.append(f"- **建议：** {strategy_stage.get('verdict', 'N/A')}")
        lines.append(f"- **信心度：** {strategy_stage.get('confidence', 'N/A')}")
        reasons = strategy_stage.get('reasons', [])
        if reasons:
            lines.append(f"- **原因：**")
            for r in reasons:
                lines.append(f"  - {r}")
        lines.append(f"- **整体风险水平：** {strategy_stage.get('overall_risk_level', 'N/A')}")
        lines.append(f"- **时间估计：** {strategy_stage.get('time_estimate', '')}")
        lines.append(f"- **预算估计：** {strategy_stage.get('budget_estimate', '')}")
        action_items = strategy_stage.get('action_items', [])
        if action_items:
            lines.append(f"- **行动项：**")
            for item in action_items:
                action = item.get('action', '')
                priority = item.get('priority', '')
                timeline = item.get('timeline', '')
                lines.append(f"  - [{priority}] {action} ({timeline})")
        lines.append(f"- **一句话结论：** {strategy_stage.get('one_liner', '')}")
        lines.append("")
    
    lines.extend([
        "## 反思总结",
    ])
    
    if ctx.reflection:
        lines.append(f"- **一致性检查：** {'通过' if ctx.reflection.get('consistency_check') else '未通过'}")
        conflicts = ctx.reflection.get('conflicts', [])
        if conflicts:
            lines.append(f"- **冲突：**")
            for c in conflicts:
                lines.append(f"  - {c}")
        lines.append(f"- **总结：** {ctx.reflection.get('summary', '')}")
        suggested_actions = ctx.reflection.get('suggested_actions', [])
        if suggested_actions:
            lines.append(f"- **建议动作：**")
            for a in suggested_actions:
                lines.append(f"  - {a}")
        lines.append(f"- **输出信心度：** {ctx.reflection.get('confidence_in_outputs', 'N/A')}")

    # --- Agent Outputs 摘要 ---
    lines.extend(["", "## Agent Outputs（按角色）", ""])

    idea = ctx.get_stage("idea_validation")
    if idea:
        lines.extend([
            "### Problem Agent",
            f"- 有效性：{'通过' if idea.get('valid') else '未通过'}　|　清晰度：{idea.get('clarity_score', '-')}/10",
            f"- 总结：{idea.get('summary', '-')}",
            "",
        ])

    market = ctx.get_stage("market_analysis")
    if market:
        lines.extend([
            "### Market Agent",
            f"- 趋势：{market.get('trend', '-')}　|　竞争：{market.get('competition_level', '-')}　|　规模：{market.get('market_size_estimate', '-')}",
            f"- 机会总结：{market.get('opportunity_summary', '-')}",
            "",
        ])

    strategy = ctx.get_stage("strategy_advice") or {}
    risk_view = {k: v for k, v in strategy.items() if k in _RISK_FIELDS}
    strat_view = {k: v for k, v in strategy.items() if k in _STRATEGY_FIELDS}

    if risk_view:
        lines.extend([
            "### Risk Agent",
            f"- 风险等级：{risk_view.get('overall_risk_level', '-')}　|　可逆性：{risk_view.get('reversibility', '-')}",
            f"- 最大损失估计：{risk_view.get('max_loss_estimate', '-')}",
        ])
        for rf in risk_view.get("risk_factors", []):
            lines.append(f"  - {rf}")
        lines.append("")

    if strat_view:
        lines.extend([
            "### Strategy Agent",
            f"- 结论：{strat_view.get('verdict', '-')}　|　信心：{strat_view.get('confidence', '-')}",
            f"- 一句话：{strat_view.get('one_liner', '-')}",
        ])
        for ai in strat_view.get("action_items", []):
            action = ai.get("action", "") if isinstance(ai, dict) else str(ai)
            lines.append(f"  - {action}")
        lines.append("")

    if ctx.reflection:
        lines.extend([
            "### Reflection Agent",
            f"- 一致性：{'通过' if ctx.reflection.get('consistency_check') else '未通过'}　|　信心：{ctx.reflection.get('confidence_in_outputs', '-')}",
            f"- 摘要：{ctx.reflection.get('summary', '-')}",
            "",
        ])

    return "\n".join(lines)


def render_status_bar(run_time: float | None, usage: dict | None):
    """渲染顶部运行状态栏。不展示 mock；Token 为轻量估算。"""
    col1, col2, col3, col4, col5 = st.columns(5)
    llm_status = get_llm_status_display()
    qwen_model = get_qwen_model_display()
    llm_calls = (usage or {}).get("llm_calls", 0)
    token_est = (usage or {}).get("token_est")

    with col1:
        st.metric("LLM 状态", llm_status)

    with col2:
        st.metric("Qwen 模型", qwen_model)

    with col3:
        st.metric("调用次数", str(llm_calls))

    with col4:
        if token_est is not None:
            st.metric("Token(估算)", str(token_est))
            st.caption("估算值，仅用于成本感知")
        else:
            st.metric("Token(估算)", "-")

    with col5:
        if run_time is not None:
            st.metric("运行耗时", f"{run_time:.2f}s")
        else:
            st.metric("运行耗时", "-")


_RISK_FIELDS = {
    "overall_risk_level", "risk_factors", "max_loss_estimate",
    "reversibility", "risk_recommendation",
}

_STRATEGY_FIELDS = {
    "verdict", "confidence", "reasons", "time_estimate", "budget_estimate",
    "key_milestones", "critical_resources", "gaps",
    "action_items", "alternatives", "one_liner",
}


def _split_strategy(stage: dict | None) -> tuple[dict, dict]:
    """将 strategy_advice 拆分为 Risk Agent 视图和 Strategy Agent 视图。"""
    if not stage:
        return {}, {}
    risk_view = {k: v for k, v in stage.items() if k in _RISK_FIELDS}
    strategy_view = {k: v for k, v in stage.items() if k in _STRATEGY_FIELDS}
    return risk_view, strategy_view


def render_core_judgment(ctx: DecisionContext):
    """核心判断：一句话结论 + 关键原因 + 下一步建议。"""
    strategy = ctx.get_stage("strategy_advice") or {}
    one_liner = strategy.get("one_liner", "")
    reasons = (strategy.get("reasons") or [])[:3]

    next_steps: list[str] = []
    if ctx.reflection:
        next_steps = list(ctx.reflection.get("suggested_actions") or [])[:3]
    if len(next_steps) < 3:
        for item in strategy.get("action_items") or []:
            if len(next_steps) >= 3:
                break
            text = item.get("action", "") if isinstance(item, dict) else str(item)
            if text and text not in next_steps:
                next_steps.append(text)

    st.subheader("核心判断")

    if one_liner:
        st.info(one_liner)
    else:
        st.caption("暂无结论")

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**关键原因**")
        if reasons:
            for i, r in enumerate(reasons, 1):
                st.markdown(f"{i}. {r}")
        else:
            st.caption("暂无")
    with col_r:
        st.markdown("**下一步建议**")
        if next_steps:
            for i, a in enumerate(next_steps, 1):
                st.markdown(f"{i}. {a}")
        else:
            st.caption("暂无")


def render_ctx_display(ctx: DecisionContext):
    """渲染决策仪表盘（产品级结构）。"""

    # ── 核心判断 ──
    render_core_judgment(ctx)

    st.divider()

    # ── 决策过程（默认折叠） ──
    with st.expander("决策过程（展开查看）", expanded=False):
        idea = ctx.get_stage("idea_validation")
        if idea:
            st.markdown("#### Stage 1：问题解析")
            st.markdown(
                f"**有效性：** {'通过' if idea.get('valid') else '未通过'}　|　"
                f"**清晰度：** {idea.get('clarity_score', '-')}/10"
            )
            st.markdown(f"**总结：** {idea.get('summary', '-')}")
            for label, key in [("假设", "assumptions"), ("缺失信息", "missing_info")]:
                items = idea.get(key) or []
                if items:
                    st.markdown(f"**{label}：** {', '.join(str(x) for x in items)}")
            if idea.get("suggested_refinement"):
                st.markdown(f"**改进建议：** {idea['suggested_refinement']}")
            st.markdown("---")

        market = ctx.get_stage("market_analysis")
        if market:
            st.markdown("#### Stage 2：市场分析")
            st.markdown(
                f"**规模：** {market.get('market_size_estimate', '-')}　|　"
                f"**趋势：** {market.get('trend', '-')}　|　"
                f"**竞争：** {market.get('competition_level', '-')}"
            )
            comps = market.get("key_competitors") or []
            if comps:
                st.markdown(f"**主要竞品：** {', '.join(str(c) for c in comps)}")
            st.markdown(f"**机会总结：** {market.get('opportunity_summary', '-')}")
            risks = market.get("risks") or []
            if risks:
                st.markdown(f"**风险：** {', '.join(str(r) for r in risks)}")
            st.markdown("---")

        strategy_raw = ctx.get_stage("strategy_advice")
        if strategy_raw:
            st.markdown("#### Stage 3：策略建议")
            st.markdown(
                f"**建议：** {strategy_raw.get('verdict', '-')}　|　"
                f"**信心：** {strategy_raw.get('confidence', '-')}　|　"
                f"**风险：** {strategy_raw.get('overall_risk_level', '-')}"
            )
            for r in (strategy_raw.get("reasons") or []):
                st.markdown(f"- {r}")
            for item in strategy_raw.get("action_items") or []:
                if isinstance(item, dict):
                    st.markdown(f"- [{item.get('priority', '')}] {item.get('action', '')} ({item.get('timeline', '')})")
                else:
                    st.markdown(f"- {item}")
            st.markdown(f"**一句话结论：** {strategy_raw.get('one_liner', '-')}")
            st.markdown("---")

        if ctx.reflection:
            st.markdown("#### 反思总结")
            st.markdown(
                f"**一致性：** {'通过' if ctx.reflection.get('consistency_check') else '未通过'}　|　"
                f"**信心：** {ctx.reflection.get('confidence_in_outputs', '-')}"
            )
            for c in ctx.reflection.get("conflicts") or []:
                st.markdown(f"- {c}")
            st.markdown(f"**总结：** {ctx.reflection.get('summary', '-')}")
            for a in ctx.reflection.get("suggested_actions") or []:
                st.markdown(f"- {a}")

    # ── Agent Outputs（标签页，JSON 隐藏在"技术详情"内） ──
    st.subheader("Agent Outputs")
    risk_view, strategy_view = _split_strategy(ctx.get_stage("strategy_advice"))

    tab_problem, tab_market, tab_risk, tab_strategy, tab_reflection = st.tabs([
        "Problem Agent", "Market Agent", "Risk Agent", "Strategy Agent", "Reflection Agent",
    ])

    with tab_problem:
        data = ctx.get_stage("idea_validation")
        if data:
            st.markdown(f"**总结：** {data.get('summary', '-')}")
            st.markdown(
                f"**有效性：** {'通过' if data.get('valid') else '未通过'}　|　"
                f"**清晰度：** {data.get('clarity_score', '-')}/10"
            )
            for label, key in [("假设", "assumptions"), ("缺失信息", "missing_info")]:
                items = data.get(key) or []
                if items:
                    st.markdown(f"**{label}：** {', '.join(str(x) for x in items)}")
            with st.expander("技术详情"):
                st.json(data)
        else:
            st.info("Problem Agent 无输出")

    with tab_market:
        data = ctx.get_stage("market_analysis")
        if data:
            st.markdown(
                f"**趋势：** {data.get('trend', '-')}　|　"
                f"**竞争：** {data.get('competition_level', '-')}　|　"
                f"**规模：** {data.get('market_size_estimate', '-')}"
            )
            st.markdown(f"**机会总结：** {data.get('opportunity_summary', '-')}")
            risks_list = data.get("risks") or []
            if risks_list:
                st.markdown(f"**风险：** {', '.join(str(r) for r in risks_list)}")
            with st.expander("技术详情"):
                st.json(data)
        else:
            st.info("Market Agent 无输出")

    with tab_risk:
        if risk_view:
            st.markdown(
                f"**风险等级：** {risk_view.get('overall_risk_level', '-')}　|　"
                f"**可逆性：** {risk_view.get('reversibility', '-')}"
            )
            st.markdown(f"**最大损失：** {risk_view.get('max_loss_estimate', '-')}")
            for f in risk_view.get("risk_factors") or []:
                st.markdown(f"- {f}")
            if risk_view.get("risk_recommendation"):
                st.markdown(f"**风险建议：** {risk_view['risk_recommendation']}")
            with st.expander("技术详情"):
                st.json(risk_view)
        else:
            st.info("Risk Agent 无输出")

    with tab_strategy:
        if strategy_view:
            st.markdown(
                f"**结论：** {strategy_view.get('verdict', '-')}　|　"
                f"**信心：** {strategy_view.get('confidence', '-')}"
            )
            st.markdown(f"**一句话：** {strategy_view.get('one_liner', '-')}")
            for r in (strategy_view.get("reasons") or []):
                st.markdown(f"- {r}")
            for item in strategy_view.get("action_items") or []:
                if isinstance(item, dict):
                    st.markdown(f"- [{item.get('priority', '')}] {item.get('action', '')} ({item.get('timeline', '')})")
                else:
                    st.markdown(f"- {item}")
            with st.expander("技术详情"):
                st.json(strategy_view)
        else:
            st.info("Strategy Agent 无输出")

    with tab_reflection:
        if ctx.reflection:
            st.markdown(
                f"**一致性：** {'通过' if ctx.reflection.get('consistency_check') else '未通过'}　|　"
                f"**信心：** {ctx.reflection.get('confidence_in_outputs', '-')}"
            )
            st.markdown(f"**总结：** {ctx.reflection.get('summary', '-')}")
            for a in ctx.reflection.get("suggested_actions") or []:
                st.markdown(f"- {a}")
            with st.expander("技术详情"):
                st.json(ctx.reflection)
        else:
            st.info("Reflection Agent 无输出")

    if ctx.error:
        st.error(ctx.error)


# ---------------------------------------------------------------------------
# 三方案对比渲染
# ---------------------------------------------------------------------------

_VARIANT_KEYS = ("baseline", "current", "aggressive")
_VARIANT_NAMES = {"baseline": "保守方案", "current": "当前方案", "aggressive": "激进方案"}
_META_LABELS = {
    "time_commitment": "时间投入",
    "budget": "资金投入",
    "validation_window": "验证周期",
    "output_frequency": "产出频率",
    "risk_exposure": "风险敞口",
    "success_metric": "成功标准",
    "constraint_compliance": "约束遵守",
}


def render_triple_result(result: dict, just_ran: bool = False) -> None:
    """渲染三方案对比：KPI 表格 → 图表 → 推荐卡片 → 详细 Tabs。"""

    if just_ran:
        render_status_bar(st.session_state.run_time, st.session_state.usage)

    # ── 1) 三方案 KPI 对比 ──
    st.subheader("三方案对比")
    cols = st.columns(3)
    for i, key in enumerate(_VARIANT_KEYS):
        report = result[key]
        with cols[i]:
            st.markdown(f"**{_VARIANT_NAMES[key]}**")
            st.metric("综合分", f"{report.decision_score}/100")
            st.metric("等级", report.grade)
            st.metric("建议", report.recommendation)
            st.metric("风险", report.risk_display)

    # ── 2) 对比图表 ──
    triple_scores: dict[str, dict[str, int]] = {}
    triple_totals: dict[str, int] = {}
    for key in _VARIANT_KEYS:
        report = result[key]
        metrics = _ensure_decision_metrics(report.ctx)
        scores = extract_subscores(metrics)
        if scores:
            triple_scores[key] = scores
        triple_totals[key] = report.decision_score

    chart_c1, chart_c2 = st.columns(2)
    with chart_c1:
        fig = build_triple_radar_chart(triple_scores)
        if fig:
            st.pyplot(fig)
            import matplotlib.pyplot as _plt
            _plt.close(fig)
        else:
            st.caption("雷达图不可用（缺少 matplotlib 或分项数据）")
    with chart_c2:
        fig = build_triple_bar_chart(triple_totals)
        if fig:
            st.pyplot(fig)
            import matplotlib.pyplot as _plt
            _plt.close(fig)
        else:
            st.caption("柱状图不可用（缺少 matplotlib 或分项数据）")

    # ── 3) 推荐卡片 ──
    rec = result.get("recommendation", {})
    if rec:
        st.subheader("推荐方案")
        rec_name = _VARIANT_NAMES.get(rec.get("recommended_key", ""), "未知")
        confidence = rec.get("confidence", 0)
        st.info(f"**{rec_name}**　|　置信度：**{confidence:.0%}**")

        col_why, col_unc = st.columns(2)
        with col_why:
            st.markdown("**推荐理由**")
            for i, w in enumerate(rec.get("why", []), 1):
                st.markdown(f"{i}. {w}")
        with col_unc:
            st.markdown("**关键不确定性**")
            for i, u in enumerate(rec.get("key_uncertainties", []), 1):
                st.markdown(f"{i}. {u}")

    st.divider()

    # ── 4) 详细结果 Tabs ──
    tabs = st.tabs([_VARIANT_NAMES[k] for k in _VARIANT_KEYS])
    for idx, key in enumerate(_VARIANT_KEYS):
        with tabs[idx]:
            report = result[key]
            meta = result.get("variants_meta", {}).get(key, {})
            if meta:
                with st.expander("方案参数"):
                    for mk, mv in meta.items():
                        st.markdown(f"- **{_META_LABELS.get(mk, mk)}**：{mv}")
            render_ctx_display(report.ctx)

    # ── 5) 导出 ──
    cur_ctx = result["current"].ctx
    combined = {k: ctx_to_dict(result[k].ctx) for k in _VARIANT_KEYS}
    combined["recommendation"] = result.get("recommendation", {})
    combined_json = json.dumps(combined, ensure_ascii=False, indent=2)
    st.download_button(
        label="导出决策档案（三方案 JSON）",
        data=combined_json,
        file_name=f"triple_{cur_ctx.id[:8]}.json",
        mime="application/json",
        key=f"dl_triple_{cur_ctx.id[:8]}",
    )


# ---------------------------------------------------------------------------
# 低碳诊断与优化建模场景
# ---------------------------------------------------------------------------

_LC_LEVELS = ["低", "中", "高"]
_LC_SCALE_LEVELS = ["小", "中", "大"]
_LC_GREEN_LEVELS = ["常规", "增强", "示范"]


def _build_lowcarbon_markdown(result: dict) -> str:
    """生成设计前期低碳备忘录 Markdown。"""
    cur = result["current"]
    tgt = result["target"]
    con = result["conservative"]
    eco = result.get("ecology", {})
    sink = result.get("carbon_sink", {})
    inp = result.get("input_summary", {})

    lines = [
        "# 设计前期低碳备忘录\n",
        "## 输入参数",
        f"- 道路等级：{inp.get('road_grade', '-')}",
        f"- 路线长度：{inp.get('length_km', '-')} km",
        f"- 车道数：{inp.get('lanes', '-')}",
        f"- 桥隧比：{inp.get('xe_pct', '-')}%\n",
        "## 三情景对比\n",
        "| 情景 | 低碳诊断指数 | 优化潜力 |",
        "|------|------------|---------|",
        f"| 当前方案 | {cur['lowcarbon_index']:.1f} | — |",
        f"| 低碳优化（Target） | {tgt['lowcarbon_index']:.1f} "
        f"| {tgt['improvement_pct']:.1f}% |",
        f"| 保守落地（Conservative） | {con['lowcarbon_index']:.1f} "
        f"| {con['improvement_pct']:.1f}% |",
        f"\n- 风险指数：{cur['risk_level']}\n",
        "## Top 3 杠杆贡献\n",
    ]
    for lev in result.get("levers", []):
        lines.append(
            f"- **{lev['factor']}**：{lev['direction']}　"
            f"影响幅度 {lev.get('impact_range', '-')}　占比 {lev['contribution_pct']:.0f}%")

    lines.append("\n## 设计动作建议\n")
    for i, sug in enumerate(result.get("design_suggestions", []), 1):
        lines.append(f"{i}. **{sug['action']}**（预计 {sug['estimated_range']}）")
        lines.append(f"   - 前置条件：{sug['prerequisite']}")

    lines.append("\n## 生态影响\n")
    lines.append(
        f"- 生态影响指数：{eco.get('index', '-')}　|　"
        f"生态风险：{eco.get('risk', '-')}")
    for s in eco.get("suggestions", []):
        lines.append(f"- {s}")

    lines.append("\n## 碳汇潜力\n")
    lines.append(f"- 碳汇潜力指数：{sink.get('index', '-')}")
    for s in sink.get("suggestions", []):
        lines.append(f"- {s}")

    lines.append("\n## 关键不确定性\n")
    for i, u in enumerate(result.get("key_uncertainties", []), 1):
        lines.append(f"{i}. {u}")

    lines.append("\n## 下一步补数清单\n")
    for i, s in enumerate(result.get("next_steps", []), 1):
        lines.append(f"{i}. {s}")

    lines += [
        "\n---",
        "*设计前期参数化估算，用于方案讨论与优化方向识别，"
        "不替代正式评价/核算结论；"
        "结果随勘察深度与设计资料完善动态更新。*\n",
    ]
    return "\n".join(lines)


def render_lowcarbon_diagnosis(result: dict) -> None:
    """渲染单方案低碳诊断 + 三情景 + 生态/碳汇结果。"""
    cur = result["current"]
    tgt = result["target"]
    con = result["conservative"]
    eco = result.get("ecology", {})
    sink = result.get("carbon_sink", {})
    inp = result.get("input_summary", {})

    # ── 综合决策卡 ──
    st.subheader("综合决策卡（设计前期）")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        st.metric("低碳诊断指数", f"{cur['lowcarbon_index']:.1f}")
    with dc2:
        st.metric("生态影响指数", f"{eco.get('index', '-')}")
    with dc3:
        st.metric("碳汇潜力指数", f"{sink.get('index', '-')}")
    st.caption(
        "推荐逻辑：优先控制生态风险（不可逆）→ "
        "再优化建设期低碳（可调）→ 最后提升绿化碳汇作为加分项")

    st.divider()

    # ── 低碳诊断 KPI ──
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("低碳诊断指数", f"{cur['lowcarbon_index']:.1f}")
    with k2:
        st.metric("风险指数", cur["risk_level"])
    with k3:
        st.metric("优化潜力（Target）", f"{tgt['improvement_pct']:.1f}%")

    # ── 情景对比 ──
    st.subheader("情景对比（自动生成）")
    cc1, cc2 = st.columns(2)
    with cc1:
        fig = build_lowcarbon_bar_chart(
            cur["lowcarbon_index"], tgt["lowcarbon_index"],
            con["lowcarbon_index"])
        if fig:
            st.pyplot(fig)
            import matplotlib.pyplot as _plt
            _plt.close(fig)
        else:
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.metric("当前方案", f"{cur['lowcarbon_index']:.1f}")
            with sc2:
                st.metric("低碳优化", f"{tgt['lowcarbon_index']:.1f}",
                          delta=f"+{tgt['improvement_pct']:.1f}%")
            with sc3:
                st.metric("保守落地", f"{con['lowcarbon_index']:.1f}",
                          delta=f"+{con['improvement_pct']:.1f}%")
    with cc2:
        fig = build_lowcarbon_radar_chart(
            cur.get("radar_scores", {}), tgt.get("radar_scores", {}))
        if fig:
            st.pyplot(fig)
            import matplotlib.pyplot as _plt
            _plt.close(fig)
        else:
            st.caption("雷达图不可用")

    # ── Top 3 杠杆 ──
    st.subheader("Top 3 杠杆贡献")
    for lev in result.get("levers", []):
        st.markdown(
            f"- **{lev['factor']}**：{lev['direction']}　"
            f"影响幅度 {lev.get('impact_range', '-')}　"
            f"占比 {lev['contribution_pct']:.0f}%")

    # ── 设计动作建议 ──
    st.subheader("设计动作建议")
    for i, sug in enumerate(result.get("design_suggestions", []), 1):
        st.markdown(
            f"{i}. **{sug['action']}**\n"
            f"   - 预计改善区间：{sug['estimated_range']}\n"
            f"   - 前置条件：{sug['prerequisite']}")

    # ── 生态 & 碳汇建议 ──
    eco_col, sink_col = st.columns(2)
    with eco_col:
        st.markdown(
            f"**生态优化建议**　"
            f"指数 {eco.get('index', '-')}　|　风险 {eco.get('risk', '-')}")
        for i, s in enumerate(eco.get("suggestions", []), 1):
            st.markdown(f"{i}. {s}")
    with sink_col:
        st.markdown(f"**碳汇规划建议**　指数 {sink.get('index', '-')}")
        for i, s in enumerate(sink.get("suggestions", []), 1):
            st.markdown(f"{i}. {s}")

    # ── 不确定性 & 补数 ──
    col_u, col_n = st.columns(2)
    with col_u:
        st.markdown("**关键不确定性**")
        for i, u in enumerate(result.get("key_uncertainties", []), 1):
            st.markdown(f"{i}. {u}")
    with col_n:
        st.markdown("**下一步补数清单**")
        for i, s in enumerate(result.get("next_steps", []), 1):
            st.markdown(f"{i}. {s}")

    # ── 详细计算过程 ──
    with st.expander("详细计算过程"):
        road_g = inp.get("road_grade", "-")
        st.markdown(
            f"#### 输入参数\n"
            f"- 道路等级：{road_g}　|　路线 {inp.get('length_km', '-')} km　|　"
            f"{inp.get('lanes', '-')} 车道　|　桥隧比 {inp.get('xe_pct', '-')}%\n"
            f"\n#### 基准估算\n"
            f"- **Ye ≈ {cur['ye']:.1f}** tCO₂e/km\n"
            f"\n#### 修正因子\n")
        for factor, val in cur["delta_breakdown"].items():
            arrow = "↑" if val > 0 else ("↓" if val < 0 else "—")
            st.markdown(f"- {factor}：{val:+.1%} {arrow}")
        st.markdown(
            f"- **Δ 合计 ≈ {cur['delta']:+.2%}**\n"
            f"- **E_est ≈ {cur['e_est']:.1f}** tCO₂e/km\n"
            f"- **低碳诊断指数 = {cur['lowcarbon_index']:.1f}**\n"
            f"\n#### 优化情景\n"
            f"- Target：E ≈ {tgt['e_value']:.1f}　→　"
            f"指数 {tgt['lowcarbon_index']:.1f}　→　"
            f"降幅 {tgt['improvement_pct']:.1f}%\n"
            f"- Conservative：E ≈ {con['e_value']:.1f}　→　"
            f"指数 {con['lowcarbon_index']:.1f}　→　"
            f"降幅 {con['improvement_pct']:.1f}%")

    # ── 免责声明 ──
    st.caption(
        "设计前期参数化估算，用于方案讨论与优化方向识别，"
        "不替代正式评价/核算结论；"
        "结果随勘察深度与设计资料完善动态更新。")

    # ── 导出 ──
    exp1, exp2 = st.columns(2)
    with exp1:
        st.download_button(
            label="导出决策档案（JSON）",
            data=json.dumps(result, ensure_ascii=False, indent=2),
            file_name="lowcarbon_diagnosis.json",
            mime="application/json",
            key="dl_lc_json",
        )
    with exp2:
        st.download_button(
            label="导出设计前期低碳备忘录（Markdown）",
            data=_build_lowcarbon_markdown(result),
            file_name="lowcarbon_memo.md",
            mime="text/markdown",
            key="dl_lc_md",
        )


def render_lowcarbon_scene() -> None:
    """低碳诊断与优化建模场景入口。"""
    from core.lowcarbon_model import run_lowcarbon_diagnosis

    st.subheader("交通工程低碳决策引擎")
    st.markdown("**公路工程场景**")
    st.caption("参考《公路工程绿色低碳建设水平评价标准》团体标准，"
               "设计前期参数化估算，不替代正式核算。")
    st.info("本系统默认不保存个人决策数据。如需保存，请使用下方「导出」功能。")

    # ── 当前设计参数 ──
    st.markdown("#### 当前设计参数")
    _ROAD_GRADES = ["高速公路", "一级公路"]
    _GRADE_DEFAULT_LANES = {"高速公路": 6, "一级公路": 4}
    _LANES_OPTIONS = [4, 6, 8]

    c1, c2, c3 = st.columns(3)
    with c1:
        length = st.number_input("路线长度 (km)", 0.1, 500.0, 10.0, 0.5, key="lc_len")
        road_grade = st.selectbox("道路等级", _ROAD_GRADES, index=0, key="lc_grade")
        default_lanes = _GRADE_DEFAULT_LANES[road_grade]
        lanes = st.selectbox(
            "车道数", _LANES_OPTIONS,
            index=_LANES_OPTIONS.index(default_lanes), key="lc_lanes")
        xe = st.slider("桥隧比 xe (%)", 0, 100, 30, key="lc_xe")
    with c2:
        earthwork = st.selectbox("土石方", _LC_LEVELS, index=1, key="lc_ew")
        transport = st.number_input("平均运距 (km)", 0.0, 300.0, 30.0, 5.0, key="lc_td")
        prefab = st.selectbox("预制率", _LC_LEVELS, index=0, key="lc_pf")
        elec = st.selectbox("电动化条件", _LC_LEVELS, index=0, key="lc_el")
    with c3:
        waste = st.selectbox("固废循环利用率", _LC_LEVELS, index=0, key="lc_wr")
        schedule = st.selectbox("工期压力", _LC_LEVELS, index=1, key="lc_sp")
        env = st.selectbox("环境敏感 / 红线风险", _LC_LEVELS, index=0, key="lc_env")
        geo = st.selectbox("地质复杂度", _LC_LEVELS, index=0, key="lc_geo")

    if road_grade == "高速公路" and lanes <= 4:
        st.warning("高速公路通常为多车道（≥6），当前车道数请确认口径。")
    elif road_grade == "一级公路" and lanes >= 8:
        st.warning("一级公路车道数偏高，请确认是否为高速口径。")

    # ── 生态影响 ──
    st.markdown("#### 生态影响评估")
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        land_scale = st.selectbox(
            "永久占地规模", _LC_SCALE_LEVELS, index=1, key="lc_land_scale")
    with ec2:
        land_sensitivity = st.selectbox(
            "占地敏感性", _LC_LEVELS, index=1, key="lc_land_sens")
    with ec3:
        involves_forest_water = st.checkbox(
            "可能涉及林地/水域", value=False, key="lc_forest")

    # ── 碳汇潜力（高级选项） ──
    with st.expander("碳汇潜力评估（高级选项）"):
        greening_intensity = st.selectbox(
            "绿化提升强度", _LC_GREEN_LEVELS, index=0, key="lc_green")

    scheme = {
        "road_grade": road_grade, "length_km": length,
        "lanes": lanes, "xe_pct": xe,
        "earthwork": earthwork, "transport_distance": transport,
        "prefab_rate": prefab, "electrification": elec,
        "waste_recycling": waste, "schedule_pressure": schedule,
        "env_sensitive": env, "geo_complexity": geo,
        "land_scale": land_scale, "land_sensitivity": land_sensitivity,
        "involves_forest_water": involves_forest_water,
        "greening_intensity": greening_intensity,
    }

    if st.button("运行低碳诊断", key="btn_lc_run"):
        with st.spinner("正在计算…"):
            result = run_lowcarbon_diagnosis(scheme)
        st.session_state.lowcarbon_result = result

    if st.session_state.get("lowcarbon_result"):
        render_lowcarbon_diagnosis(st.session_state.lowcarbon_result)


def main() -> None:
    st.set_page_config(page_title="AI Decision OS", layout="wide")
    st.title("AI Decision OS")
    st.subheader("结构化决策操作系统")
    
    render_status_bar(st.session_state.run_time, st.session_state.usage)
    
    st.divider()

    st.markdown("**请选择决策子模块**")
    scene = st.radio(
        "选择场景",
        ["创业 / 副业决策", "交通工程低碳决策"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if scene == "交通工程低碳决策":
        render_lowcarbon_scene()
        return

    # ── 创业决策：模块化输入 ──
    st.subheader("创业 / 副业决策建模")
    st.info("本系统默认不保存个人决策数据。如需保存，请使用下方「导出决策档案」功能。")

    # A. 核心问题
    question = st.text_input(
        "你想决策的问题（一句话）",
        placeholder="例如：我该不该辞职做 AI 自媒体？",
    )

    # B. 现状 / 资源 / 约束
    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        inp_status = st.text_area(
            "现状",
            placeholder="例如：在职产品经理，月薪 2w，工作 3 年",
            height=100,
        )
    with col_b2:
        inp_resource = st.text_area(
            "可用资源",
            placeholder="例如：有 10w 积蓄，懂 Python，有 2k 粉小红书号",
            height=100,
        )
    with col_b3:
        inp_constraint = st.text_area(
            "约束条件",
            placeholder="例如：房贷 5k/月，不能全职投入超过 6 个月",
            height=100,
        )

    # C. 最在意什么
    concern_options = ["亏钱", "浪费时间", "方向选错", "社交压力", "不够 AI / 技术壁垒不足"]
    concerns = st.multiselect(
        "你最在意什么？（可多选）",
        options=concern_options,
        default=[],
        placeholder="选择你最担心的风险…",
    )

    # D. 期限
    col_d, col_e = st.columns(2)
    with col_d:
        deadline = st.selectbox(
            "期望验证周期",
            options=["1 个月", "3 个月", "6 个月", "1 年"],
            index=1,
        )
    # E. 成功标准
    with col_e:
        success_criteria = st.text_input(
            "成功标准",
            placeholder="例如：3 个月内月收入 5k / 验证 PMF",
        )

    # F. 补充说明
    extra_note = st.text_area(
        "补充说明（可选）",
        placeholder="任何你觉得对决策有帮助的信息…",
        height=80,
    )

    # G. 扩展决策空间
    expand_mode = st.checkbox("扩展决策空间（自动生成 保守 / 当前 / 激进 对比）", value=False)

    # 拼接 background —— 保持后端接口不变
    def _assemble_background() -> str:
        parts: list[str] = []
        if inp_status.strip():
            parts.append(f"【现状】{inp_status.strip()}")
        if inp_resource.strip():
            parts.append(f"【资源】{inp_resource.strip()}")
        if inp_constraint.strip():
            parts.append(f"【约束】{inp_constraint.strip()}")
        if concerns:
            parts.append(f"【最在意】{', '.join(concerns)}")
        if deadline:
            parts.append(f"【期望周期】{deadline}")
        if success_criteria.strip():
            parts.append(f"【成功标准】{success_criteria.strip()}")
        if extra_note.strip():
            parts.append(f"【补充】{extra_note.strip()}")
        return "\n".join(parts)

    just_ran = False
    if st.button("运行决策引擎"):
        if not question.strip():
            st.warning("请填写问题")
            return

        background = _assemble_background()

        if expand_mode:
            context_dict = {
                "status": inp_status.strip(),
                "resource": inp_resource.strip(),
                "constraint": inp_constraint.strip(),
                "concerns": concerns,
                "deadline": deadline,
                "success_criteria": success_criteria.strip(),
                "extra": extra_note.strip(),
            }
            with st.spinner("正在生成三方案对比（保守 / 当前 / 激进）…"):
                triple = run_decision_space_expand(
                    question=question.strip(),
                    background=background,
                    context_dict=context_dict,
                )
            total_usage: dict = {"llm_calls": 0, "token_est": 0}
            for _k in ("baseline", "current", "aggressive"):
                _u = triple[_k].usage
                total_usage["llm_calls"] += _u.get("llm_calls", 0)
                total_usage["token_est"] += _u.get("token_est", 0)
            st.session_state.triple_result = triple
            st.session_state.current_ctx = None
            st.session_state.run_time = triple["elapsed_time"]
            st.session_state.usage = total_usage
        else:
            with st.spinner("执行中…"):
                report = run_decision(
                    question=question.strip(),
                    background=background,
                )
            st.session_state.current_ctx = report.ctx
            st.session_state.triple_result = None
            st.session_state.run_time = report.elapsed_time
            st.session_state.usage = report.usage

        just_ran = True

    # ── 展示结果 ──
    if st.session_state.triple_result:
        render_triple_result(st.session_state.triple_result, just_ran)

    elif st.session_state.current_ctx:
        show_ctx = st.session_state.current_ctx
        show_metrics = _ensure_decision_metrics(show_ctx)

        if just_ran:
            render_status_bar(st.session_state.run_time, st.session_state.usage)

        st.subheader("决策指数")
        render_kpi(show_metrics)

        render_ctx_display(show_ctx)

        col1, col2 = st.columns(2)
        ctx_dict_json = json.dumps(ctx_to_dict(show_ctx), ensure_ascii=False, indent=2)
        with col1:
            st.download_button(
                label="导出决策档案（JSON）",
                data=ctx_dict_json,
                file_name=f"decision_{show_ctx.id[:8]}.json",
                mime="application/json",
                key=f"dl_json_result_{show_ctx.id[:8]}",
            )
        with col2:
            markdown_content = generate_markdown_report(show_ctx)
            ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            st.download_button(
                label="导出决策档案（Markdown）",
                data=markdown_content,
                file_name=f"decision_report_{ts}.md",
                mime="text/markdown",
                key=f"dl_md_result_{show_ctx.id[:8]}",
            )


if __name__ == "__main__":
    main()
