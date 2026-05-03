"""URL 规范化：把同一资源的不同 URL 形式归一化到同一字符串，作为去重 key。

按 source 类型分别处理：

  weixin     mp.weixin.qq.com/s/<sn>     去全部 query（scene/chksm/key/...）
  youtube    统一成 youtube.com/watch?v=<id>，去 list/t/index/si/pp...
  bilibili   保留 path（含 BV 号），去 query
  xiaoyuzhou 保留 path（含 episode id），去 query
  ximalaya   保留 path，去 query
  x_twitter  统一成 x.com/<user>/status/<id>，去 query
  webpage    保留 scheme+host+path+sorted query（去 utm_*/fbclid/gclid 等追踪参数）
  本地路径    Path.resolve() 后转 posix 字符串

任何非平凡的归一化失败时，回退到原 URL（保守策略）。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .router import InputType


# 通用追踪/分享参数（任何 webpage 都该剥掉）
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_brand", "utm_social",
    "fbclid", "gclid", "dclid", "msclkid", "yclid",
    "share_source", "share_medium", "share_plat",
    "share_session_id", "weibo_id", "share_token",
    "_hsenc", "_hsmi", "mc_cid", "mc_eid",
    "ref", "ref_", "referer",
}

def _strip_query(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _normalize_weixin(url: str) -> str:
    """微信永久链：mp.weixin.qq.com/s/<sn>，所有 query 都是会话参数。"""
    p = urlparse(url)
    return urlunparse((p.scheme.lower() or "https", p.netloc.lower(), p.path, "", "", ""))


def _normalize_youtube(url: str) -> str:
    """统一成 https://www.youtube.com/watch?v=<id>"""
    p = urlparse(url)
    host = p.netloc.lower()
    vid = ""
    if host in ("youtu.be", "www.youtu.be"):
        # https://youtu.be/<id>
        seg = p.path.strip("/").split("/")
        if seg and seg[0]:
            vid = seg[0]
    else:
        # https://(www|m).youtube.com/watch?v=<id>  或  /shorts/<id> / /embed/<id>
        path_lower = p.path.lower()
        if path_lower.startswith("/shorts/") or path_lower.startswith("/embed/"):
            seg = p.path.strip("/").split("/")
            if len(seg) >= 2:
                vid = seg[1]
        else:
            qs = dict(parse_qsl(p.query, keep_blank_values=False))
            vid = qs.get("v", "")
    if not vid:
        # 拿不到 v 参数就退回保守去 query
        return _strip_query(url)
    return f"https://www.youtube.com/watch?v={vid}"


def _normalize_bilibili(url: str) -> str:
    """B 站 BV 号在 path 里，去 query 即可。b23.tv 短链不展开（让 yt-dlp 自己处理）。"""
    p = urlparse(url)
    host = p.netloc.lower()
    return urlunparse((p.scheme.lower() or "https", host, p.path.rstrip("/"), "", "", ""))


def _normalize_podcast_path(url: str) -> str:
    """小宇宙 / 喜马拉雅：episode id 在 path 里。"""
    p = urlparse(url)
    return urlunparse((p.scheme.lower() or "https", p.netloc.lower(), p.path.rstrip("/"), "", "", ""))


def _normalize_x_twitter(url: str) -> str:
    """统一 host 到 x.com，去 query。"""
    p = urlparse(url)
    host = p.netloc.lower()
    if host in ("twitter.com", "www.twitter.com", "mobile.twitter.com"):
        host = "x.com"
    elif host == "www.x.com":
        host = "x.com"
    return urlunparse((p.scheme.lower() or "https", host, p.path.rstrip("/"), "", "", ""))


def _normalize_webpage(url: str) -> str:
    """通用网页：剥追踪参数、规范化大小写、去 fragment。"""
    p = urlparse(url)
    host = p.netloc.lower()
    pairs = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    ]
    pairs.sort()
    return urlunparse(
        (p.scheme.lower() or "https", host, p.path or "/", "", urlencode(pairs), "")
    )


def canonicalize(input_value: str, source_type: InputType) -> str:
    """根据 source 类型规范化输入。失败时回退原值。"""
    try:
        if source_type == InputType.WEIXIN:
            return _normalize_weixin(input_value)
        if source_type == InputType.YOUTUBE:
            return _normalize_youtube(input_value)
        if source_type == InputType.PODCAST:
            host = urlparse(input_value).netloc.lower()
            if "bilibili.com" in host or host.endswith("b23.tv"):
                return _normalize_bilibili(input_value)
            return _normalize_podcast_path(input_value)
        if source_type == InputType.X_TWITTER:
            return _normalize_x_twitter(input_value)
        if source_type == InputType.WEBPAGE:
            return _normalize_webpage(input_value)
        if source_type in (
            InputType.LOCAL_EPUB, InputType.LOCAL_PDF, InputType.LOCAL_OFFICE,
            InputType.LOCAL_IMAGE, InputType.LOCAL_AUDIO, InputType.LOCAL_ZIP,
            InputType.LOCAL_DATA, InputType.LOCAL_TEXT,
        ):
            return _normalize_local_path(input_value)
        # SEARCH / UNKNOWN：原样返回
        return input_value
    except Exception:  # noqa: BLE001
        return input_value


def _normalize_local_path(path: str) -> str:
    p = Path(path).expanduser()
    try:
        return p.resolve().as_posix()
    except OSError:
        return os.path.abspath(path).replace("\\", "/")
