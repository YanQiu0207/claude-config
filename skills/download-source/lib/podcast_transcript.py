"""播客 / 视频 / 音频转写（Get笔记 OpenAPI，移植自原项目）。

支持平台（凡是 Get笔记后端能识别的链接均可）：
  - 小宇宙 xiaoyuzhoufm.com
  - 喜马拉雅 ximalaya.com
  - B 站 bilibili.com
  - 其他音频/视频外链

凭证：
  环境变量 GETNOTE_API_KEY / GETNOTE_CLIENT_ID（OpenAPI 长期 key）
  ~/.claude/skills/getnote/tokens.json（Web JWT，90 天 refresh_token）
  缺失任一时返回 success=False，由调用方决定降级策略（如 yt-dlp 下音频）。

原参考实现：
  https://github.com/joeseesun/qiaomu-anything-to-notebooklm/blob/main/scripts/get_podcast_transcript.py
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


GETNOTE_OPENAPI_BASE = "https://openapi.biji.com"
GETNOTE_WEB_REFRESH = "https://notes-api.biji.com/account/v2/web/user/auth/refresh"
GETNOTE_WEB_DETAIL = "https://get-notes.luojilab.com/voicenotes/web/notes/{note_id}/links/detail"
TOKENS_FILE = Path.home() / ".claude" / "skills" / "getnote" / "tokens.json"


@dataclass
class PodcastResult:
    success: bool
    txt_path: str = ""
    title: str = ""
    content: str = ""
    note_id: str = ""
    strategy_used: str = ""
    error: str = ""


class GetNoteCredsMissing(RuntimeError):
    pass


def _api_error(prefix: str, payload: dict[str, Any]) -> str:
    """把 API 失败响应压成无敏感字段的短错误。"""
    parts: list[str] = []
    header = payload.get("h")
    if isinstance(header, dict):
        code = header.get("c")
        message = header.get("m") or header.get("msg")
        if code is not None:
            parts.append(f"code={code}")
        if message:
            parts.append(f"message={message}")
    for key in ("code", "error_code", "message", "msg"):
        value = payload.get(key)
        if value is not None and value != "":
            parts.append(f"{key}={value}")
    return f"{prefix}: {', '.join(parts)}" if parts else prefix


def _check_creds() -> tuple[str, str]:
    api_key = os.environ.get("GETNOTE_API_KEY")
    client_id = os.environ.get("GETNOTE_CLIENT_ID")
    if not api_key or not client_id:
        raise GetNoteCredsMissing(
            "GETNOTE_API_KEY / GETNOTE_CLIENT_ID 未设置（播客转写依赖 Get笔记 OpenAPI）。"
        )
    return api_key, client_id


def _openapi_call(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: int = 30,
) -> dict[str, Any]:
    api_key, client_id = _check_creds()
    headers = {
        "Authorization": api_key,
        "X-Client-ID": client_id,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = requests.request(
        method,
        GETNOTE_OPENAPI_BASE + path,
        headers=headers,
        json=body if body is not None else None,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def _load_tokens() -> dict[str, Any]:
    if not TOKENS_FILE.exists():
        raise GetNoteCredsMissing(
            f"Token 文件不存在：{TOKENS_FILE}\n"
            "需要从浏览器导出 token（参考原项目说明）。"
        )
    return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))


def _save_tokens(tokens: dict[str, Any]) -> None:
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2), encoding="utf-8")


def _refresh_jwt(refresh_token: str, *, timeout: int = 20) -> dict[str, Any]:
    r = requests.post(
        GETNOTE_WEB_REFRESH,
        headers={
            "Content-Type": "application/json",
            "Origin": "https://www.biji.com",
            "Referer": "https://www.biji.com/",
        },
        json={"refresh_token": refresh_token},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("h", {}).get("c") != 0:
        raise RuntimeError(_api_error("Token refresh failed", data))
    return data["c"]


def _get_valid_jwt(*, timeout: int = 30) -> str:
    tokens = _load_tokens()
    now = int(time.time())
    if now >= tokens.get("refresh_token_expire_at", 0):
        raise RuntimeError(
            "refresh_token 已过期（90 天有效），需要重新从浏览器导出 token。"
        )
    if now >= tokens.get("token_expire_at", 0) - 300:
        new_info = _refresh_jwt(tokens["refresh_token"], timeout=timeout)
        tokens.update(
            {
                "token": new_info["token"],
                "token_expire_at": new_info["token_expire_at"],
                "refresh_token": new_info.get("refresh_token", tokens["refresh_token"]),
                "refresh_token_expire_at": new_info.get(
                    "refresh_token_expire_at", tokens["refresh_token_expire_at"]
                ),
            }
        )
        _save_tokens(tokens)
    return tokens["token"]


def _fetch_transcript(note_id: str, *, timeout: int = 30) -> dict[str, Any]:
    jwt = _get_valid_jwt(timeout=timeout)
    r = requests.get(
        GETNOTE_WEB_DETAIL.format(note_id=note_id),
        headers={
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
            "Origin": "https://www.biji.com",
            "Referer": "https://www.biji.com/",
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("h", {}).get("c") != 0:
        raise RuntimeError(_api_error("Transcript fetch failed", data))
    return data["c"]


def fetch_podcast_transcript(
    podcast_url: str,
    out_dir: Path,
    *,
    poll_interval: int = 30,
    max_polls: int = 40,
    request_timeout: int = 30,
) -> PodcastResult:
    """完整流程：建笔记 → 轮询任务 → 拉取转写 → 写 TXT。

    Args:
        podcast_url: 平台链接（小宇宙/喜马拉雅/B 站/其他）
        out_dir: 输出目录
        poll_interval: 轮询间隔（秒）
        max_polls: 最大轮询次数（默认 40 × 30s = 20 分钟）
    """
    try:
        _check_creds()
    except GetNoteCredsMissing as e:
        return PodcastResult(
            success=False,
            strategy_used="getnote_creds_missing",
            error=str(e),
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        resp = _openapi_call(
            "POST",
            "/open/api/v1/resource/note/save",
            {"note_type": "link", "link_url": podcast_url},
            timeout=request_timeout,
        )
    except (requests.RequestException, RuntimeError) as e:
        return PodcastResult(success=False, strategy_used="getnote_create_failed", error=str(e))

    if not resp.get("success"):
        return PodcastResult(
            success=False,
            strategy_used="getnote_create_failed",
            error=_api_error("create note failed", resp),
        )

    tasks = resp.get("data", {}).get("tasks", []) or []
    if not tasks:
        return PodcastResult(
            success=False,
            strategy_used="getnote_no_task",
            error="No tasks returned by /resource/note/save",
        )
    first = tasks[0] if isinstance(tasks[0], dict) else None
    task_id = first.get("task_id") if first else None
    if not task_id:
        return PodcastResult(
            success=False,
            strategy_used="getnote_no_task_id",
            error="tasks[0] has no task_id",
        )

    note_id: int | str | None = None
    last_status = ""
    for i in range(max_polls):
        if i > 0:
            time.sleep(poll_interval)
        try:
            prog = _openapi_call(
                "POST",
                "/open/api/v1/resource/note/task/progress",
                {"task_id": task_id},
                timeout=request_timeout,
            )
        except (requests.RequestException, RuntimeError) as e:
            return PodcastResult(
                success=False,
                strategy_used="getnote_progress_failed",
                error=f"poll {i+1}: {e}",
            )
        last_status = prog.get("data", {}).get("status", "")
        if last_status == "success":
            note_id = prog["data"].get("note_id")
            break
        if last_status == "failed":
            return PodcastResult(
                success=False,
                strategy_used="getnote_task_failed",
                error="Get笔记 task reported failed",
            )

    if note_id is None:
        return PodcastResult(
            success=False,
            strategy_used="getnote_timeout",
            error=f"Transcription timed out after {max_polls * poll_interval}s, last_status={last_status}",
        )

    try:
        result = _fetch_transcript(str(note_id), timeout=request_timeout)
    except (requests.RequestException, RuntimeError) as e:
        return PodcastResult(
            success=False,
            strategy_used="getnote_detail_failed",
            error=str(e),
            note_id=str(note_id),
        )

    title = result.get("web_title") or result.get("title") or "未知标题"
    content = result.get("content") or ""
    if not content:
        return PodcastResult(
            success=False,
            strategy_used="getnote_empty",
            error="No transcript content returned",
            note_id=str(note_id),
            title=title,
        )

    txt_path = out_dir / "transcript.txt"
    txt_path.write_text(
        f"# {title}\n\n来源: {podcast_url}\n笔记ID: {note_id}\n"
        f"获取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{content}",
        encoding="utf-8",
    )

    return PodcastResult(
        success=True,
        txt_path=str(txt_path),
        title=title,
        content=content,
        note_id=str(note_id),
        strategy_used="getnote",
    )
