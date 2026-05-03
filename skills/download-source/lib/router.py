"""输入识别 + 路由分发。

InputType 与原项目 main.py:detect_input_type 保持一致 + 扩展 csv/json/xml。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class InputType(str, Enum):
    WEIXIN = "weixin"
    YOUTUBE = "youtube"
    PODCAST = "podcast"          # 小宇宙/喜马拉雅/B 站
    X_TWITTER = "x_twitter"
    WEBPAGE = "webpage"          # 通用网页 + 付费墙
    LOCAL_EPUB = "local_epub"
    LOCAL_PDF = "local_pdf"
    LOCAL_OFFICE = "local_office"  # docx/pptx/xlsx
    LOCAL_IMAGE = "local_image"
    LOCAL_AUDIO = "local_audio"
    LOCAL_ZIP = "local_zip"
    LOCAL_DATA = "local_data"     # csv/json/xml/html
    LOCAL_TEXT = "local_text"     # md/txt
    SEARCH = "search"
    UNKNOWN = "unknown"


@dataclass
class RouteDecision:
    input_type: InputType
    canonical: str  # URL（标准化）或绝对路径


WEIXIN_HOSTS = ("mp.weixin.qq.com",)
YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")
PODCAST_HOSTS = (
    "xiaoyuzhoufm.com", "www.xiaoyuzhoufm.com",
    "ximalaya.com", "www.ximalaya.com",
    "bilibili.com", "www.bilibili.com",
    "b23.tv",
)
X_TWITTER_HOSTS = (
    "x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com",
)


def _host_in(url: str, hosts: tuple[str, ...]) -> bool:
    return urlparse(url).netloc.lower() in hosts


def _is_url(value: str) -> bool:
    v = value.strip().lower()
    return v.startswith("http://") or v.startswith("https://")


def detect(input_value: str) -> RouteDecision:
    """识别一个输入参数。"""
    raw = input_value.strip()
    if not raw:
        return RouteDecision(InputType.UNKNOWN, raw)

    # URL 优先
    if _is_url(raw):
        if _host_in(raw, WEIXIN_HOSTS):
            return RouteDecision(InputType.WEIXIN, raw)
        if _host_in(raw, YOUTUBE_HOSTS):
            return RouteDecision(InputType.YOUTUBE, raw)
        if _host_in(raw, PODCAST_HOSTS):
            return RouteDecision(InputType.PODCAST, raw)
        if _host_in(raw, X_TWITTER_HOSTS):
            return RouteDecision(InputType.X_TWITTER, raw)
        return RouteDecision(InputType.WEBPAGE, raw)

    # 本地路径
    p = Path(raw).expanduser()
    if p.exists() and p.is_file():
        suffix = p.suffix.lower()
        abs_path = str(p.resolve())
        if suffix == ".epub":
            return RouteDecision(InputType.LOCAL_EPUB, abs_path)
        if suffix == ".pdf":
            return RouteDecision(InputType.LOCAL_PDF, abs_path)
        if suffix in (".docx", ".pptx", ".xlsx"):
            return RouteDecision(InputType.LOCAL_OFFICE, abs_path)
        if suffix in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            return RouteDecision(InputType.LOCAL_IMAGE, abs_path)
        if suffix in (".mp3", ".wav"):
            return RouteDecision(InputType.LOCAL_AUDIO, abs_path)
        if suffix == ".zip":
            return RouteDecision(InputType.LOCAL_ZIP, abs_path)
        if suffix in (".csv", ".json", ".xml", ".html", ".htm"):
            return RouteDecision(InputType.LOCAL_DATA, abs_path)
        if suffix in (".md", ".txt"):
            return RouteDecision(InputType.LOCAL_TEXT, abs_path)
        return RouteDecision(InputType.UNKNOWN, abs_path)

    # 既不是 URL 也不是已存在文件 → 当搜索关键词
    return RouteDecision(InputType.SEARCH, raw)


def detect_all(values: list[str]) -> list[RouteDecision]:
    return [detect(v) for v in values]
