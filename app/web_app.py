"""
Streamlit 演示层（最小可运行）。
从项目根目录运行: streamlit run app/web_app.py
支持 Mock / Qwen；每次运行后自动保存 session 到 data/sessions，并提供下载。
"""
from __future__ import annotations

import json
import os
import sys
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

from core import DecisionContext, Engine
from agents import (
    IdeaValidatorAgent,
    MarketAnalyzerAgent,
    StrategyAdvisorAgent,
    ReflectorAgent,
)

SESSIONS_DIR = ROOT / "data" / "sessions"

# 读取运行时 provider 配置
def get_provider_display() -> str:
    """获取 provider 显示文本。"""
    provider = (os.getenv("LLM_PROVIDER") or "mock").strip().lower()
    if provider == "qwen":
        api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
        model = (os.getenv("QWEN_MODEL") or "qwen-plus").strip()
        if not api_key:
            return f"qwen({model}, 未配置key, 将回退mock)"
        return f"qwen({model})"
    return provider


def ctx_to_dict(ctx: DecisionContext) -> dict:
    """将 DecisionContext 序列化为可 JSON 的 dict（不修改 context 结构）。"""
    return asdict(ctx)


def ensure_sessions_dir() -> Path:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return SESSIONS_DIR


def save_session(ctx: DecisionContext) -> tuple[str, str]:
    """
    保存 ctx 到 data/sessions，文件名含时间戳与短 id（Windows 兼容，无冒号）。
    返回 (文件路径, 文件内容 JSON 字符串)。
    """
    ensure_sessions_dir()
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    short_id = (ctx.id or "unknown")[:8]
    filename = f"{ts}_{short_id}.json"
    filepath = SESSIONS_DIR / filename
    data = ctx_to_dict(ctx)
    content = json.dumps(data, ensure_ascii=False, indent=2)
    filepath.write_text(content, encoding="utf-8")
    return str(filepath), content


def main() -> None:
    st.set_page_config(page_title="Decision Engine v0.1", layout="wide")
    st.title("Decision Engine Core v0.1")
    provider_display = get_provider_display()
    st.caption(f"4 Agent 闭环（当前: {provider_display}，失败自动回退 Mock）")

    question = st.text_input("你的问题", placeholder="例如：是否该做 XX 副业？")
    background = st.text_area("背景（可选）", placeholder="简单描述现状、资源、约束…")
    if st.button("运行决策引擎"):
        if not question.strip():
            st.warning("请填写问题")
            return

        ctx = DecisionContext(
            user_input={
                "question": question.strip(),
                "background": (background or "").strip(),
                "constraints": [],
            }
        )

        registry = {
            "idea_validation": IdeaValidatorAgent(),
            "market_analysis": MarketAnalyzerAgent(),
            "strategy_advice": StrategyAdvisorAgent(),
        }
        reflector = ReflectorAgent()
        engine = Engine(agent_registry=registry, reflector=reflector)

        with st.spinner("执行中…"):
            ctx = engine.run(ctx)

        st.success(f"状态: {ctx.status}")

        # 会话持久化：无论 Mock 还是 Qwen 都保存
        try:
            saved_path, json_content = save_session(ctx)
            st.info(f"会话已保存: `{saved_path}`")
            st.download_button(
                label="下载本次会话 JSON",
                data=json_content,
                file_name=Path(saved_path).name,
                mime="application/json",
            )
        except Exception as e:
            st.warning(f"保存会话失败: {e}")

        for stage_id in ctx.stages_order:
            with st.expander(f"Stage: {stage_id}", expanded=(stage_id == ctx.stages_order[0])):
                st.json(ctx.get_stage(stage_id) or {})

        if ctx.reflection:
            st.subheader("Reflection")
            st.json(ctx.reflection)

        if ctx.error:
            st.error(ctx.error)


if __name__ == "__main__":
    main()
