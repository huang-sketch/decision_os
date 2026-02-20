"""
用量估算（仅标准库，不做真实 token 统计）。
提供 LLM 状态展示、调用次数与 Token 估算，并写入 ctx.extra["usage"]。
"""
from __future__ import annotations

import json
import os
from typing import Any

# 4 个 Agent：3 stages + 1 reflector
NUM_AGENT_CALLS = 4


def _env_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "").strip().lower()


def _env_qwen_key() -> str:
    return (os.getenv("DASHSCOPE_API_KEY") or "").strip()


def _env_qwen_model() -> str:
    return (os.getenv("QWEN_MODEL") or "qwen-plus").strip()


def get_llm_status_display() -> str:
    """
    获取 LLM 状态展示文案，不向用户暴露 mock。
    - 若 LLM_PROVIDER=qwen 且存在 DASHSCOPE_API_KEY：Qwen（{QWEN_MODEL}）
    - 否则：LLM未就绪（已回退）
    """
    if _env_provider() == "qwen" and _env_qwen_key():
        return f"Qwen（{_env_qwen_model()}）"
    return "LLM未就绪（已回退）"


def get_llm_calls() -> int:
    """本次运行中 LLM 实际调用次数（若走回退则为 0）。"""
    if _env_provider() == "qwen" and _env_qwen_key():
        return NUM_AGENT_CALLS
    return 0


def estimate_tokens(ctx: Any) -> int:
    """
    轻量估算：token_est ~= (prompt_approx + output_approx) / 2。
    基于 ctx 内 user_input、stages、reflection 的文本长度估算。
    """
    def _len(d: Any) -> int:
        return len(json.dumps(d, ensure_ascii=False))

    user_input = getattr(ctx, "user_input", None) or {}
    stages = getattr(ctx, "stages", None) or {}
    stages_order = getattr(ctx, "stages_order", [])
    reflection = getattr(ctx, "reflection", None)

    prompt_approx = _len(user_input)
    output_approx = 0
    for k in stages_order:
        stage = stages.get(k) or {}
        output_approx += _len(stage)
    if reflection:
        output_approx += _len(reflection)

    # (prompt_approx + output_approx) / 2 四舍五入为 int
    total_prompt_approx = prompt_approx * NUM_AGENT_CALLS + output_approx
    token_est = int(round((total_prompt_approx + output_approx) / 2))
    return max(0, token_est)


def build_usage(ctx: Any) -> dict[str, Any]:
    """计算 llm_calls 与 token_est，返回供写入 ctx.extra[\"usage\"] 的 dict。"""
    return {
        "llm_calls": get_llm_calls(),
        "token_est": estimate_tokens(ctx),
    }
