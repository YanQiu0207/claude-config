"""下载索引：E:/work/downloads/_index.json，供去重用。

格式：
    {
      "<canonical_url_or_path>": {
        "first_input": "<原始输入>",
        "source_type": "weixin",
        "title": "...",
        "fetched_at": "...",
        "dir": "E:/work/downloads/weixin/.../",
        "files_count": 12,
        "size_bytes": 892994
      },
      ...
    }

写入用 `os.replace` 原子化（先写 .tmp 再 rename），避免半截写损坏索引。
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


INDEX_FILE_NAME = "_index.json"
LOCK_FILE_NAME = "_index.lock"
LOCK_TIMEOUT_SECONDS = 10.0


def _index_path(out_base: Path) -> Path:
    return out_base / INDEX_FILE_NAME


def _lock_path(out_base: Path) -> Path:
    return out_base / LOCK_FILE_NAME


@contextmanager
def _index_lock(out_base: Path):
    out_base.mkdir(parents=True, exist_ok=True)
    lock = _lock_path(out_base)
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for index lock: {lock}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(lock)
        except OSError:
            pass


def load(out_base: Path) -> dict[str, dict[str, Any]]:
    """读索引。文件不存在 / 损坏时返回空字典。"""
    p = _index_path(out_base)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def lookup(out_base: Path, canonical: str) -> dict[str, Any] | None:
    """按 canonical key 查询，返回索引项或 None。

    若索引项里的 dir 已被手动删除，自动剔除并返回 None（自愈）。
    """
    idx = load(out_base)
    entry = idx.get(canonical)
    if not entry:
        return None
    d = entry.get("dir")
    if d and not Path(d).exists():
        # 自愈：dir 不存在了，删除该项。
        with _index_lock(out_base):
            fresh = load(out_base)
            if canonical in fresh:
                fresh.pop(canonical, None)
                _save_atomic(out_base, fresh)
        return None
    return entry


def record(
    out_base: Path,
    canonical: str,
    *,
    first_input: str,
    source_type: str,
    title: str,
    fetched_at: str,
    dir_path: str,
    files_count: int,
    size_bytes: int,
) -> None:
    """记录一次成功下载。同 canonical 多次记录会覆盖（始终指向最新一次）。"""
    with _index_lock(out_base):
        idx = load(out_base)
        idx[canonical] = {
            "first_input": first_input,
            "source_type": source_type,
            "title": title,
            "fetched_at": fetched_at,
            "dir": dir_path,
            "files_count": files_count,
            "size_bytes": size_bytes,
        }
        _save_atomic(out_base, idx)


def _save_atomic(out_base: Path, idx: dict[str, Any]) -> None:
    out_base.mkdir(parents=True, exist_ok=True)
    target = _index_path(out_base)
    fd, tmp = tempfile.mkstemp(prefix=".index-", suffix=".json.tmp", dir=str(out_base))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
        os.replace(tmp, target)
    except OSError:
        # 失败时尽量清理
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
