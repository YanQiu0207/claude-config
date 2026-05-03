#!/usr/bin/env python3
"""download-source 技能 CLI。

接受多个 URL 或本地路径，统一下载/转换并落到 E:/work/downloads/。

用法：
    python download.py <input1> [<input2> ...] [选项]

选项：
    --out-base DIR              输出根目录，默认 E:/work/downloads/
    --podcast-audio-only        播客只下音频，不调 Get笔记 API
    --youtube-subs-only         YouTube 只下字幕，不下视频/音频
    --no-paywall-bypass         禁用付费墙绕过策略，仅 L1 jina
    --timeout SEC               单源超时，默认 60
    --batch-label TEXT          多源时为 batch 目录追加标签
    --force                     忽略去重索引，强制重新下载
    --no-cache                  本次执行既不读也不写去重索引

退出码：
    0   全部成功
    1   全部失败
    2   部分失败
   75   archive.today 命中 CAPTCHA（同原 fetch_url.sh 约定）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 让脚本能 import lib/
_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

from lib import index as idx_mod
from lib import output as out_mod
from lib.fetch_url import ArchiveCaptcha, FetchResult, fetch_url
from lib.local_convert import LocalResult, convert_local
from lib.podcast_transcript import PodcastResult, fetch_podcast_transcript
from lib.router import InputType, RouteDecision, detect
from lib.url_canonical import canonicalize
from lib.weixin import WeixinResult, fetch_weixin
from lib.youtube_dl import YtDlpResult, download_audio, download_youtube

MAX_META_ERROR_CHARS = 500


# ── 单源处理 ───────────────────────────────────────────────────


def _handle_one(
    decision: RouteDecision,
    out_dir: Path,
    *,
    podcast_audio_only: bool,
    youtube_subs_only: bool,
    enable_paywall_bypass: bool,
    timeout: int,
) -> dict[str, Any]:
    """处理单个源，返回 meta dict。

    错误时也返回 meta（success=False、strategy_used 标记原因）。
    archive CAPTCHA 不在此层吞掉，由调用方决定退出码。
    """
    t = decision.input_type
    raw = decision.canonical

    if t in (InputType.WEBPAGE, InputType.X_TWITTER):
        return _h_webpage(raw, out_dir, t, enable_paywall_bypass, timeout)
    if t == InputType.WEIXIN:
        return _h_weixin(raw, out_dir, timeout)
    if t == InputType.YOUTUBE:
        return _h_youtube(raw, out_dir, youtube_subs_only)
    if t == InputType.PODCAST:
        return _h_podcast(raw, out_dir, podcast_audio_only, timeout)
    if t in (
        InputType.LOCAL_EPUB,
        InputType.LOCAL_PDF,
        InputType.LOCAL_OFFICE,
        InputType.LOCAL_IMAGE,
        InputType.LOCAL_AUDIO,
        InputType.LOCAL_ZIP,
        InputType.LOCAL_DATA,
        InputType.LOCAL_TEXT,
    ):
        return _h_local(raw, out_dir, t)
    if t == InputType.SEARCH:
        return _result_meta(
            source_type="search",
            input_value=raw,
            title=raw,
            strategy_used="search_pending",
            files=[],
            extras={
                "note": (
                    "search 关键词需要由 skill 主对话先调 WebSearch 拿到 URL，"
                    "再把这批 URL 重新作为多源输入传给本 CLI。"
                ),
            },
            success=False,
        )
    return _result_meta(
        source_type="unknown",
        input_value=raw,
        title="",
        strategy_used="unknown",
        files=[],
        success=False,
    )


def _sanitize_error(error: str) -> str:
    if not error:
        return ""
    first_part = str(error).split("Traceback (most recent call last):", 1)[0].strip()
    text = first_part or str(error).splitlines()[-1].strip()
    if len(text) > MAX_META_ERROR_CHARS:
        text = f"{text[:MAX_META_ERROR_CHARS]}... [truncated]"
    return text


def _result_meta(
    *,
    source_type: str,
    input_value: str,
    title: str,
    strategy_used: str,
    files: list[str],
    paywall_bypassed: bool = False,
    extras: dict[str, Any] | None = None,
    success: bool,
    error: str = "",
) -> dict[str, Any]:
    meta = out_mod.build_meta(
        source_type=source_type,
        input_value=input_value,
        title=title,
        strategy_used=strategy_used,
        files=files,
        paywall_bypassed=paywall_bypassed,
        extras=extras,
    )
    meta["success"] = success
    if error:
        meta["error"] = _sanitize_error(error)
    return meta


def _h_webpage(
    url: str,
    out_dir: Path,
    t: InputType,
    enable_paywall_bypass: bool,
    timeout: int,
) -> dict[str, Any]:
    source_type = "webpage" if t == InputType.WEBPAGE else "x_twitter"
    try:
        result: FetchResult = fetch_url(
            url, timeout=timeout, enable_paywall_bypass=enable_paywall_bypass
        )
    except ArchiveCaptcha as e:
        # 不吞，往上抛
        raise
    if not result.success:
        return _result_meta(
            source_type=source_type,
            input_value=url,
            title="",
            strategy_used=result.strategy_used or "failed",
            files=[],
            success=False,
            error=result.error,
        )
    md_path = out_mod.write_text_file(out_dir, "content.md", result.content)
    return _result_meta(
        source_type=source_type,
        input_value=url,
        title=result.title or "",
        strategy_used=result.strategy_used,
        files=[str(md_path)],
        paywall_bypassed=result.paywall_bypassed,
        extras=result.extras,
        success=True,
    )


def _h_weixin(url: str, out_dir: Path, timeout: int) -> dict[str, Any]:
    res: WeixinResult = fetch_weixin(url, out_dir, timeout=timeout)
    if not res.success:
        return _result_meta(
            source_type="weixin",
            input_value=url,
            title="",
            strategy_used=res.strategy_used,
            files=[],
            success=False,
            error=res.error,
        )
    return _result_meta(
        source_type="weixin",
        input_value=url,
        title=res.title,
        strategy_used=res.strategy_used,
        files=res.files,
        extras={
            "author": res.author,
            "publish_time": res.publish_time,
            "cover_url": res.cover_url,
        },
        success=True,
    )


def _h_youtube(url: str, out_dir: Path, subs_only: bool) -> dict[str, Any]:
    res: YtDlpResult = download_youtube(url, out_dir, subs_only=subs_only)
    if not res.success:
        return _result_meta(
            source_type="youtube",
            input_value=url,
            title="",
            strategy_used=res.strategy_used,
            files=[],
            success=False,
            error=res.error,
        )
    return _result_meta(
        source_type="youtube",
        input_value=url,
        title=res.title,
        strategy_used=res.strategy_used,
        files=res.files,
        extras=res.extras,
        success=True,
    )


def _h_podcast(url: str, out_dir: Path, audio_only: bool, timeout: int) -> dict[str, Any]:
    if audio_only:
        a = download_audio(url, out_dir)
        if not a.success:
            return _result_meta(
                source_type="podcast",
                input_value=url,
                title="",
                strategy_used=a.strategy_used,
                files=[],
                success=False,
                error=a.error,
            )
        return _result_meta(
            source_type="podcast",
            input_value=url,
            title=a.title,
            strategy_used=a.strategy_used,
            files=a.files,
            extras={**a.extras, "degraded": True, "reason": "audio_only requested"},
            success=True,
        )

    p: PodcastResult = fetch_podcast_transcript(url, out_dir, request_timeout=timeout)
    if p.success:
        return _result_meta(
            source_type="podcast",
            input_value=url,
            title=p.title,
            strategy_used=p.strategy_used,
            files=[p.txt_path],
            extras={"note_id": p.note_id, "content_length": len(p.content)},
            success=True,
        )
    # Get笔记不可用 → 自动降级到音频
    a = download_audio(url, out_dir)
    if a.success:
        return _result_meta(
            source_type="podcast",
            input_value=url,
            title=a.title,
            strategy_used=a.strategy_used,
            files=a.files,
            extras={
                **a.extras,
                "degraded": True,
                "reason": f"getnote unavailable: {p.error}",
            },
            success=True,
        )
    return _result_meta(
        source_type="podcast",
        input_value=url,
        title="",
        strategy_used="podcast_all_failed",
        files=[],
        success=False,
        error=f"getnote: {p.error} | yt_dlp: {a.error}",
    )


def _h_local(path: str, out_dir: Path, t: InputType) -> dict[str, Any]:
    res: LocalResult = convert_local(Path(path), out_dir)
    src_map = {
        InputType.LOCAL_EPUB: "local_epub",
        InputType.LOCAL_PDF: "local_pdf",
        InputType.LOCAL_OFFICE: "local_office",
        InputType.LOCAL_IMAGE: "local_image",
        InputType.LOCAL_AUDIO: "local_audio",
        InputType.LOCAL_ZIP: "local_zip",
        InputType.LOCAL_DATA: "local_data",
        InputType.LOCAL_TEXT: "local_text",
    }
    source_type = src_map[t]
    if not res.success:
        return _result_meta(
            source_type=source_type,
            input_value=path,
            title="",
            strategy_used=res.strategy_used,
            files=[],
            success=False,
            error=res.error,
        )
    return _result_meta(
        source_type=source_type,
        input_value=path,
        title=res.title,
        strategy_used=res.strategy_used,
        files=res.files,
        success=True,
    )


def _dispatch(
    dec: RouteDecision,
    dest_dir: Path,
    *,
    podcast_audio_only: bool,
    youtube_subs_only: bool,
    enable_paywall_bypass: bool,
    timeout: int,
) -> tuple[dict[str, Any], str | None]:
    """运行单个源（含异常包装），返回 meta 和可选 CAPTCHA URL。"""
    try:
        return (
            _handle_one(
                dec,
                dest_dir,
                podcast_audio_only=podcast_audio_only,
                youtube_subs_only=youtube_subs_only,
                enable_paywall_bypass=enable_paywall_bypass,
                timeout=timeout,
            ),
            None,
        )
    except ArchiveCaptcha as e:
        return (
            _result_meta(
                source_type=dec.input_type.value,
                input_value=dec.canonical,
                title="",
                strategy_used="archive_captcha",
                files=[],
                success=False,
                error=f"archive.today CAPTCHA at {e.archive_url}",
            ),
            e.archive_url,
        )
    except Exception as e:  # noqa: BLE001
        return (
            _result_meta(
                source_type=dec.input_type.value,
                input_value=dec.canonical,
                title="",
                strategy_used="exception",
                files=[],
                success=False,
                error=f"{type(e).__name__}: {e}",
            ),
            None,
        )


def _build_cached_meta(
    dec: RouteDecision, canonical: str, entry: dict[str, Any]
) -> dict[str, Any]:
    """从索引项构造一个 cache hit 的 meta，不创建任何新目录。"""
    return {
        "source_type": entry.get("source_type", dec.input_type.value),
        "input": dec.canonical,
        "title": entry.get("title", ""),
        "fetched_at": entry.get("fetched_at", ""),
        "strategy_used": "cached",
        "paywall_bypassed": False,
        "files": [],
        "size_bytes": entry.get("size_bytes", 0),
        "extras": {
            "cached": True,
            "canonical": canonical,
            "first_input": entry.get("first_input", ""),
            "files_count": entry.get("files_count", 0),
            "hint": "命中去重索引，未重新下载。加 --force 强制重抓。",
        },
        "success": True,
        "_dir": entry.get("dir", ""),
    }


def _maybe_record(
    *,
    out_base: Path,
    no_cache: bool,
    dec: RouteDecision,
    canonical: str,
    meta: dict[str, Any],
    dir_path: Path,
) -> None:
    """成功且开启索引时登记。"""
    if no_cache:
        return
    if not meta.get("success"):
        return
    if meta.get("strategy_used") == "cached":
        return
    files = meta.get("files") or []
    idx_mod.record(
        out_base,
        canonical,
        first_input=dec.canonical,
        source_type=str(meta.get("source_type", dec.input_type.value)),
        title=str(meta.get("title", "")),
        fetched_at=str(meta.get("fetched_at", out_mod.now_iso())),
        dir_path=str(dir_path),
        files_count=len(files),
        size_bytes=int(meta.get("size_bytes", 0) or 0),
    )


def _rename_with_title(meta: dict[str, Any], dir_path: Path) -> Path:
    """下载完成后，用真实 title 重命名目录，并把 meta.files 里的旧路径重映射到新目录。"""
    if not meta.get("success"):
        return dir_path
    new_dir = out_mod.rename_dir_with_title(dir_path, meta.get("title"))
    if new_dir == dir_path:
        return dir_path
    old_str = str(dir_path)
    new_str = str(new_dir)
    files = meta.get("files") or []
    meta["files"] = [
        f.replace(old_str, new_str, 1) if isinstance(f, str) else f for f in files
    ]
    return new_dir


def _try_cache(
    *,
    out_base: Path,
    force: bool,
    no_cache: bool,
    canonical: str,
    dec: RouteDecision,
) -> dict[str, Any] | None:
    if force or no_cache:
        return None
    if dec.input_type == InputType.SEARCH or dec.input_type == InputType.UNKNOWN:
        return None
    entry = idx_mod.lookup(out_base, canonical)
    if not entry:
        return None
    print(
        f"[cached] {dec.input_type.value}: {dec.canonical[:60]} → {entry.get('dir')}",
        file=sys.stderr,
    )
    return _build_cached_meta(dec, canonical, entry)


# ── 主入口 ─────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="多源内容下载 CLI")
    parser.add_argument("inputs", nargs="+", help="URL 或文件路径，可以多个")
    parser.add_argument("--out-base", default=None, help="输出根目录，默认 E:/work/downloads/")
    parser.add_argument("--podcast-audio-only", action="store_true")
    parser.add_argument("--youtube-subs-only", action="store_true")
    parser.add_argument("--no-paywall-bypass", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--batch-label", default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="忽略去重索引，强制重新下载（保留旧时间戳目录）",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="不读不写去重索引（一次性绕过，不污染索引）",
    )
    args = parser.parse_args(argv)

    out_base = out_mod.resolve_out_base(args.out_base)
    out_base.mkdir(parents=True, exist_ok=True)

    decisions = [detect(v) for v in args.inputs]
    canonicals = [canonicalize(d.canonical, d.input_type) for d in decisions]
    is_batch = len(decisions) > 1

    captcha_url: str | None = None
    metas: list[dict[str, Any]] = []

    if is_batch:
        ts = out_mod.now_ts()
        batch_dir = out_mod.make_batch_dir(out_base, label=args.batch_label, ts=ts)
        print(f"[batch dir] {batch_dir}", file=sys.stderr)

        for i, (dec, canonical) in enumerate(zip(decisions, canonicals), start=1):
            print(
                f"[{i}/{len(decisions)}] {dec.input_type.value}: {dec.canonical[:80]}",
                file=sys.stderr,
            )
            cached = _try_cache(
                out_base=out_base,
                force=args.force,
                no_cache=args.no_cache,
                canonical=canonical,
                dec=dec,
            )
            if cached is not None:
                metas.append(cached)
                continue

            child = out_mod.make_batch_child(batch_dir, i, dec.input_type.value, dec.canonical)
            meta, captcha = _dispatch(
                dec,
                child,
                podcast_audio_only=args.podcast_audio_only,
                youtube_subs_only=args.youtube_subs_only,
                enable_paywall_bypass=not args.no_paywall_bypass,
                timeout=args.timeout,
            )
            captcha_url = captcha_url or captcha
            child = _rename_with_title(meta, child)
            out_mod.write_meta(child, meta)
            meta["_dir"] = str(child)
            _maybe_record(
                out_base=out_base,
                no_cache=args.no_cache,
                dec=dec,
                canonical=canonical,
                meta=meta,
                dir_path=child,
            )
            metas.append(meta)

        batch_meta = {
            "batch_dir": str(batch_dir),
            "fetched_at": out_mod.now_iso(),
            "label": args.batch_label or "",
            "total": len(decisions),
            "succeeded": sum(1 for m in metas if m.get("success")),
            "failed": sum(1 for m in metas if not m.get("success")),
            "cached": sum(1 for m in metas if m.get("strategy_used") == "cached"),
            "items": metas,
        }
        (batch_dir / "batch_meta.json").write_text(
            json.dumps(batch_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(batch_meta, ensure_ascii=False, indent=2))
    else:
        dec = decisions[0]
        canonical = canonicals[0]
        cached = _try_cache(
            out_base=out_base,
            force=args.force,
            no_cache=args.no_cache,
            canonical=canonical,
            dec=dec,
        )
        if cached is not None:
            metas.append(cached)
            print(json.dumps(cached, ensure_ascii=False, indent=2))
        else:
            single_dir = out_mod.make_single_dir(out_base, dec.input_type.value, dec.canonical)
            print(f"[single dir] {single_dir}", file=sys.stderr)
            meta, captcha = _dispatch(
                dec,
                single_dir,
                podcast_audio_only=args.podcast_audio_only,
                youtube_subs_only=args.youtube_subs_only,
                enable_paywall_bypass=not args.no_paywall_bypass,
                timeout=args.timeout,
            )
            captcha_url = captcha_url or captcha
            single_dir = _rename_with_title(meta, single_dir)
            out_mod.write_meta(single_dir, meta)
            meta["_dir"] = str(single_dir)
            _maybe_record(
                out_base=out_base,
                no_cache=args.no_cache,
                dec=dec,
                canonical=canonical,
                meta=meta,
                dir_path=single_dir,
            )
            metas.append(meta)
            print(json.dumps(meta, ensure_ascii=False, indent=2))

    if captcha_url:
        print(f"ARCHIVE_CAPTCHA:{captcha_url}", file=sys.stderr)
        print(
            "archive.today 需要人工验证。请在浏览器中打开上述 URL 解 CAPTCHA 后重试本命令。",
            file=sys.stderr,
        )
        return 75

    succeeded = sum(1 for m in metas if m.get("success"))
    if succeeded == len(metas):
        return 0
    if succeeded == 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
