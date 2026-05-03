"""YouTube 下载（yt-dlp 封装）。

默认行为（老板拍板）：完整视频 + 音频 + 字幕（含自动字幕）+ info.json。
可选 subs_only=True 时只下字幕和元数据，跳过视频/音频。

也可作为兜底用于小宇宙/喜马拉雅/B 站等支持 yt-dlp 的播客平台
（fetch_audio_only=True 时只下音频）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yt_dlp  # type: ignore
except ImportError:  # pragma: no cover
    yt_dlp = None


@dataclass
class YtDlpResult:
    success: bool
    title: str = ""
    info_path: str = ""
    files: list[str] = field(default_factory=list)
    strategy_used: str = ""
    error: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


def _build_options(
    out_dir: Path,
    *,
    subs_only: bool,
    audio_only: bool,
) -> dict[str, Any]:
    """组装 yt-dlp 选项。

    输出模板用 %(id)s 而不是标题，避免 Windows 路径里的非法字符踩坑。
    后续读 info.json 拿到原始 title。
    """
    out_tpl = str(out_dir / "%(id)s.%(ext)s")

    opts: dict[str, Any] = {
        "outtmpl": out_tpl,
        "writeinfojson": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["zh-Hans", "zh-Hant", "zh-CN", "zh-TW", "zh", "en"],
        "subtitlesformat": "srt/best",
        "convertsubtitles": "srt",
        "ignoreerrors": False,
        "quiet": False,
        "no_warnings": False,
        "noprogress": True,
    }

    if subs_only:
        opts["skip_download"] = True
    elif audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        # 完整视频+音频（合并到 mp4，需要 ffmpeg）
        opts["format"] = "bv*+ba/best"
        opts["merge_output_format"] = "mp4"

    return opts


def download_youtube(
    url: str,
    out_dir: Path,
    *,
    subs_only: bool = False,
) -> YtDlpResult:
    """下载 YouTube 视频。"""
    return _run_yt_dlp(url, out_dir, subs_only=subs_only, audio_only=False, source="youtube")


def download_audio(
    url: str,
    out_dir: Path,
) -> YtDlpResult:
    """音频兜底：用于播客 Get笔记不可用时。"""
    return _run_yt_dlp(url, out_dir, subs_only=False, audio_only=True, source="podcast_audio")


def _run_yt_dlp(
    url: str,
    out_dir: Path,
    *,
    subs_only: bool,
    audio_only: bool,
    source: str,
) -> YtDlpResult:
    if yt_dlp is None:
        return YtDlpResult(
            success=False,
            strategy_used="yt_dlp_missing",
            error="yt-dlp not installed. Run: pip install yt-dlp",
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = _build_options(out_dir, subs_only=subs_only, audio_only=audio_only)
    pre_existing = {f.resolve() for f in out_dir.iterdir() if f.is_file()}

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:  # noqa: BLE001
        return YtDlpResult(
            success=False,
            strategy_used="yt_dlp_failed",
            error=f"{type(e).__name__}: {e}",
        )

    if not info:
        return YtDlpResult(
            success=False,
            strategy_used="yt_dlp_empty",
            error="yt-dlp returned no info",
        )

    title = info.get("title") or info.get("id") or "untitled"

    files: list[str] = []
    info_path = ""
    for f in sorted(out_dir.iterdir()):
        if f.is_file() and f.name != "meta.json":
            resolved = f.resolve()
            if resolved in pre_existing and not f.name.endswith(".info.json"):
                continue
            files.append(str(f))
            if f.name.endswith(".info.json"):
                info_path = str(f)

    extras: dict[str, Any] = {
        "video_id": info.get("id"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "webpage_url": info.get("webpage_url") or url,
    }

    return YtDlpResult(
        success=True,
        title=title,
        info_path=info_path,
        files=files,
        strategy_used=f"yt_dlp_{source}",
        extras=extras,
    )
