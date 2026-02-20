"""
会话存储管理：读取、排序、加载历史会话。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def list_sessions(sessions_dir: Path, limit: int = 20) -> list[tuple[str, str]]:
    """
    列出历史会话，按时间倒序，返回最近 limit 条。
    返回: [(文件名, 显示名), ...]
    """
    if not sessions_dir.exists():
        return []
    
    sessions = []
    for filepath in sessions_dir.glob("*.json"):
        filename = filepath.name
        # 文件名格式：2026-02-16T15-30-10_xxx.json
        # 提取时间部分用于排序
        try:
            time_part = filename.split("_")[0]
            sessions.append((filename, time_part))
        except Exception:
            continue
    
    # 按时间倒序排序（最新的在前）
    sessions.sort(key=lambda x: x[1], reverse=True)
    return sessions[:limit]


def load_session(sessions_dir: Path, filename: str) -> dict[str, Any] | None:
    """加载指定会话 JSON 文件。"""
    filepath = sessions_dir / filename
    if not filepath.exists():
        return None
    try:
        content = filepath.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception:
        return None


def format_session_display_name(filename: str) -> str:
    """格式化会话显示名：时间 + ID。"""
    try:
        # 2026-02-16T15-30-10_xxx.json -> 2026-02-16 15:30:10 (xxx)
        parts = filename.replace(".json", "").split("_", 1)
        if len(parts) == 2:
            time_str = parts[0].replace("T", " ").replace("-", ":")
            short_id = parts[1][:8]
            return f"{time_str} ({short_id})"
        return filename
    except Exception:
        return filename
