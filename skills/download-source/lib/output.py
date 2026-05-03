"""统一输出布局：目录约定、文件命名、meta.json 写入。

输出根：默认 E:/work/downloads/

单源：
    <root>/<source_type>/<时间戳>-<slug>/
        content.md|txt|srt | info.json | media files | assets/ | meta.json

多源（batch）：
    <root>/batch-<时间戳>/
        batch_meta.json
        source_01-<type>-<slug>/...
        source_02-<type>-<slug>/...
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from slugify import slugify as _slugify
except ImportError:  # pragma: no cover
    _slugify = None


DEFAULT_OUT_BASE = Path("E:/work/downloads")
TS_FORMAT = "%Y%m%d-%H%M%S"
MAX_SLUG_BYTES = 120


def now_ts() -> str:
    return _dt.datetime.now().strftime(TS_FORMAT)


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def safe_slug(text: str | None, max_len: int = 60) -> str:
    """把任意字符串转成文件系统安全的 slug，保留中文。

    优先用 python-slugify（保留 unicode 字母），失败时退化为正则。
    """
    if not text:
        return "untitled"
    text = text.strip()
    if _slugify is not None:
        try:
            s = _slugify(
                text,
                max_length=max_len,
                lowercase=False,
                allow_unicode=True,
                separator="-",
            )
            s = _clean_slug(s, max_len=max_len)
            if s:
                return s
        except Exception:  # noqa: BLE001
            pass
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", text)
    return _clean_slug(s, max_len=max_len) or "untitled"


def _clean_slug(text: str, *, max_len: int) -> str:
    s = text.replace("\x00", "")
    s = re.sub(r"\s+", "-", s).strip("-_.")
    if not s or set(s) == {"."}:
        return "untitled"
    return _limit_utf8_bytes(s[:max_len], MAX_SLUG_BYTES) or "untitled"


def _limit_utf8_bytes(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip("-_.")


def ensure_unique_dir(parent: Path, name: str) -> Path:
    """确保目录唯一：name 冲突时追加 -2 / -3 后缀。"""
    target = parent / name
    if not target.exists():
        target.mkdir(parents=True, exist_ok=False)
        return target
    i = 2
    while True:
        cand = parent / f"{name}-{i}"
        if not cand.exists():
            cand.mkdir(parents=True, exist_ok=False)
            return cand
        i += 1


def make_single_dir(
    out_base: Path,
    source_type: str,
    title: str | None,
    ts: str | None = None,
) -> Path:
    """单源输出目录：<out_base>/<source_type>/<ts>-<slug>/"""
    ts = ts or now_ts()
    slug = safe_slug(title)
    parent = out_base / source_type
    parent.mkdir(parents=True, exist_ok=True)
    return ensure_unique_dir(parent, f"{ts}-{slug}")


def make_batch_dir(out_base: Path, label: str | None = None, ts: str | None = None) -> Path:
    """多源输出目录：<out_base>/batch-<ts>[-label]/"""
    ts = ts or now_ts()
    name = f"batch-{ts}"
    if label:
        name = f"{name}-{safe_slug(label, max_len=30)}"
    out_base.mkdir(parents=True, exist_ok=True)
    return ensure_unique_dir(out_base, name)


def make_batch_child(batch_dir: Path, idx: int, source_type: str, title: str | None) -> Path:
    """batch 下的子源目录：source_NN-<type>-<slug>/"""
    slug = safe_slug(title)
    name = f"source_{idx:02d}-{source_type}-{slug}"
    return ensure_unique_dir(batch_dir, name)


def write_meta(target_dir: Path, meta: dict[str, Any]) -> Path:
    """写 meta.json，覆盖。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "meta.json"
    path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_meta(
    *,
    source_type: str,
    input_value: str,
    title: str | None,
    strategy_used: str,
    files: list[str],
    paywall_bypassed: bool = False,
    extras: dict[str, Any] | None = None,
    size_bytes: int | None = None,
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "input": input_value,
        "title": title or "",
        "fetched_at": now_iso(),
        "strategy_used": strategy_used,
        "paywall_bypassed": paywall_bypassed,
        "files": files,
        "size_bytes": size_bytes if size_bytes is not None else _dir_size(files),
        "extras": extras or {},
    }


def _dir_size(files: list[str]) -> int:
    total = 0
    for f in files:
        try:
            total += os.path.getsize(f)
        except OSError:
            pass
    return total


def write_text_file(target_dir: Path, name: str, content: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    p = target_dir / name
    p.write_text(content, encoding="utf-8")
    return p


def resolve_out_base(arg: str | os.PathLike[str] | None) -> Path:
    if not arg:
        return DEFAULT_OUT_BASE
    return Path(arg)


# 单源目录前缀：<YYYYMMDD-HHMMSS>-
_SINGLE_PREFIX_RE = re.compile(r"^(\d{8}-\d{6})-")
# 多源 batch_child 前缀：source_NN-<type>-
_BATCH_PREFIX_RE = re.compile(r"^(source_\d{2,}-[a-z_]+)-")


def rename_dir_with_title(dir_path: Path, title: str | None) -> Path:
    """根据真实 title 重命名目录，把 URL 派生的 slug 升级为文章标题 slug。

    保留时间戳/批次前缀不变。如果 title 为空、新名等于旧名、目标冲突无法处理或
    操作失败，原路返回 dir_path。
    """
    if not title or not dir_path.exists():
        return dir_path
    new_slug = safe_slug(title)
    if not new_slug or new_slug == "untitled":
        return dir_path

    name = dir_path.name
    m = _SINGLE_PREFIX_RE.match(name) or _BATCH_PREFIX_RE.match(name)
    if not m:
        return dir_path

    new_base = f"{m.group(1)}-{new_slug}"
    if new_base == name:
        return dir_path

    parent = dir_path.parent
    target = parent / new_base
    if target.exists():
        i = 2
        while True:
            cand = parent / f"{new_base}-{i}"
            if not cand.exists():
                target = cand
                break
            i += 1

    try:
        dir_path.rename(target)
    except OSError:
        return dir_path
    return target
