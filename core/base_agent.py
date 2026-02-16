"""
BaseAgent 统一接口，强约束 JSON 输出。
v0.1: 支持 Mock 与 Qwen（DashScope）；默认 Mock，失败自动回退 Mock。
"""
from __future__ import annotations

import json
import os
import re
from abc import ABC
from typing import Any

from .context import DecisionContext
from .schemas import validate_stage_output

# 环境变量（在首次使用时加载 dotenv，避免 engine/context 依赖）
def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _get_llm_provider() -> str:
    _load_env()
    return (os.getenv("LLM_PROVIDER") or "mock").strip().lower()


class MockLLM:
    """占位 LLM：返回预设的符合 schema 的 JSON。"""

    def __init__(self, stage_id: str, default_output: dict[str, Any]):
        self.stage_id = stage_id
        self.default_output = default_output

    def complete(self, _prompt: str, _ctx_view: dict[str, Any]) -> dict[str, Any]:
        return dict(self.default_output)


class QwenLLM:
    """通义千问（DashScope）：强制 JSON 输出，解析失败则重试一次，仍失败则回退 default_output。"""

    JSON_ONLY_INSTRUCTION = "请只输出一个 JSON 对象，不要任何多余文字、Markdown 或代码块。"

    def __init__(self, stage_id: str, default_output: dict[str, Any]):
        self.stage_id = stage_id
        self.default_output = default_output
        _load_env()
        self.api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
        self.model = (os.getenv("QWEN_MODEL") or "qwen-plus").strip()

    def complete(self, prompt: str, ctx_view: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return dict(self.default_output)
        full_prompt = f"{prompt}\n\n{self.JSON_ONLY_INSTRUCTION}"
        for attempt in range(2):
            text = self._call_api(full_prompt)
            if not text:
                continue
            parsed = self._parse_json(text)
            if parsed is not None and isinstance(parsed, dict):
                return parsed
        return dict(self.default_output)

    def _call_api(self, prompt: str) -> str | None:
        try:
            import dashscope
            from dashscope import Generation
            from http import HTTPStatus
            dashscope.api_key = self.api_key
            response = Generation.call(
                model=self.model,
                prompt=prompt,
                result_format="message",
            )
            if response.status_code != HTTPStatus.OK or not getattr(response, "output", None):
                return None
            out = response.output
            if getattr(out, "text", None):
                return out.text
            choices = getattr(out, "choices", None) or []
            if choices and getattr(choices[0], "message", None) and getattr(choices[0].message, "content", None):
                return choices[0].message.content
            return None
        except Exception:
            return None

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        text = (text or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试提取第一个 JSON 对象
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None


def _create_llm(stage_id: str, default_output: dict[str, Any]) -> MockLLM | QwenLLM:
    provider = _get_llm_provider()
    if provider == "qwen":
        return QwenLLM(stage_id, default_output)
    return MockLLM(stage_id, default_output)


class BaseAgent(ABC):
    """Agent 基类：run(ctx) -> dict，输出必须符合该 Agent 的 schema。"""

    def __init__(self, stage_id: str, default_output: dict[str, Any]):
        self.stage_id = stage_id
        self.llm = _create_llm(stage_id, default_output)

    def run(self, ctx: DecisionContext) -> dict[str, Any]:
        view = ctx.to_readonly_view()
        prompt = self._build_prompt(ctx, view)
        out = self.llm.complete(prompt, view)
        if not validate_stage_output(self.stage_id, out):
            raise ValueError(f"Agent {self.stage_id} output does not match schema: {out}")
        return out

    def _build_prompt(self, ctx: DecisionContext, view: dict[str, Any]) -> str:
        """子类可覆盖，用于真实 LLM 时的 prompt 构建。"""
        q = view.get("user_input", {}).get("question", "")
        bg = view.get("user_input", {}).get("background", "")
        parts = [f"当前阶段: {self.stage_id}", f"用户问题: {q}"]
        if bg:
            parts.append(f"背景: {bg}")
        if view.get("stages"):
            parts.append("已有阶段结果（供参考）:")
            for sid, data in view["stages"].items():
                parts.append(f"  {sid}: {json.dumps(data, ensure_ascii=False)[:500]}")
        return "\n".join(parts)
