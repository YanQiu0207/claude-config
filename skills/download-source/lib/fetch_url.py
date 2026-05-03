"""通用 URL 抓取（含付费墙绕过 6 层级联）。

Python 重写自原 fetch_url.sh：
https://github.com/joeseesun/qiaomu-anything-to-notebooklm/blob/main/scripts/fetch_url.sh

策略层级（每层失败/不满足即降级）：

  L1  r.jina.ai / defuddle.md  代理服务（覆盖广，含付费墙）
  L2  Googlebot UA + JSON-LD articleBody（域名匹配 GOOGLEBOT_DOMAINS）
      Bingbot UA  + JSON-LD articleBody（域名匹配 BINGBOT_DOMAINS）
  L3  通用付费墙绕过（域名匹配 PAYWALL_DOMAINS）：
      Googlebot+XFF / Bingbot / Facebook Ref / t.co Ref / AMP / 随机 EU IP
  L4  archive.today/newest/<URL>（CAPTCHA 检测，命中时抛 ArchiveCaptcha）
  L5  Google Cache (webcache.googleusercontent.com)
  L6  npx --yes --package @teng-lin/agent-fetch@0.1.6 agent-fetch <url> --json
      （需要 Node.js）

成功判定：
  - 行数 > 8、字符数 > 500
  - 不含付费墙关键词
  - 不含明显错误页关键词
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

from .paywall_domains import (
    is_amp_site,
    is_bingbot_site,
    is_facebook_ref_site,
    is_googlebot_site,
    is_paywall_site,
)


CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
BINGBOT_UA = (
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
)
ARCHIVE_BASE = "https://archive.today/newest/"
AGENT_FETCH_PACKAGE = "@teng-lin/agent-fetch@0.1.6"
MAX_CURL_RESPONSE_BYTES = 10 * 1024 * 1024

PAYWALL_KEYWORDS_RE = re.compile(
    r"subscribe to (continue|read|access|unlock)|paywall|premium[._]content|"
    r"metered[._]paywall|article[._]limit|sign[._]in[._]to[._](continue|read)|"
    r"create[._]a[._]free[._]account[._]to[._]unlock|"
    r"membership[._]to[._]continue|subscribe now for full access|"
    r"to continue reading|remaining free articles|has been removed|"
    r"subscribe or|already a subscriber",
    re.IGNORECASE,
)
CAPTCHA_KEYWORDS_RE = re.compile(
    r"security check|captcha|recaptcha|hcaptcha|please complete|"
    r"cloudflare.*challenge|verify you are human",
    re.IGNORECASE,
)
ERROR_PAGE_KEYWORDS = (
    "Don't miss what's happening",
    "Access Denied",
    "404 Not Found",
    "403 Forbidden",
)
# 处理 JSON 字符串里的转义引号 `\"`：避免 articleBody 含引号时被截断
JSONLD_ARTICLE_BODY_RE = re.compile(r'"articleBody"\s*:\s*"((?:[^"\\]|\\.)*)"')
TITLE_TAG_RE = re.compile(r"<title[^>]*>([^<]*)</title>", re.IGNORECASE)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
NAV_FOOTER_RE = re.compile(r"<(nav|footer|header)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
HTML_ENTITY_MAP = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&nbsp;": " ",
}


class ArchiveCaptcha(RuntimeError):
    """archive.today 命中 CAPTCHA，需要老板手动开页解决。"""

    def __init__(self, archive_url: str) -> None:
        super().__init__(f"archive.today CAPTCHA: {archive_url}")
        self.archive_url = archive_url


@dataclass
class FetchResult:
    success: bool
    content: str = ""
    title: str = ""
    strategy_used: str = ""
    paywall_bypassed: bool = False
    error: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


def _has_content(text: str) -> bool:
    if not text:
        return False
    if len(text) < 500:
        return False
    if text.count("\n") < 8:
        return False
    for kw in ERROR_PAGE_KEYWORDS:
        if kw in text:
            return False
    return True


def _is_paywall(text: str) -> bool:
    return bool(PAYWALL_KEYWORDS_RE.search(text))


def _is_captcha(text: str) -> bool:
    return bool(CAPTCHA_KEYWORDS_RE.search(text))


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    s = SCRIPT_STYLE_RE.sub("", html)
    s = NAV_FOOTER_RE.sub("", s)
    s = TAG_RE.sub("", s)
    for k, v in HTML_ENTITY_MAP.items():
        s = s.replace(k, v)
    s = re.sub(r"[\t ]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _extract_jsonld_article(html: str) -> str:
    if not html:
        return ""
    m = JSONLD_ARTICLE_BODY_RE.search(html)
    if not m:
        return ""
    body = m.group(1)
    return (
        body.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
    )


def _extract_title(html: str) -> str:
    if not html:
        return ""
    m = TITLE_TAG_RE.search(html)
    if not m:
        return ""
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()


def _extract_md_title(markdown: str) -> str:
    """从 Markdown 文本里抽 title。

    按以下优先级在前 80 行内尝试：
      1. jina/defuddle 伪 frontmatter：`Title: Xxx`
      2. YAML frontmatter：`title: Xxx`（位于 `---` 之间）
      3. ATX H1：`# Xxx`
    """
    if not markdown:
        return ""
    lines = markdown.splitlines()[:80]

    # 1. jina / defuddle 头部 `Title: Xxx`
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.lower().startswith("title:"):
            return s.split(":", 1)[1].strip()
        # jina 的头部块只在最前几行，遇到正文内容就停止匹配
        if s.startswith("#") or s.startswith("-") or s.startswith("*"):
            break

    # 2. YAML frontmatter title
    if lines and lines[0].strip() == "---":
        for line in lines[1:60]:
            s = line.strip()
            if s == "---":
                break
            if s.lower().startswith("title:"):
                v = s.split(":", 1)[1].strip()
                return v.strip("\"'")

    # 3. ATX H1
    for line in lines:
        s = line.strip()
        if s.startswith("# ") and not s.startswith("# #"):
            return s[2:].strip()

    return ""


def _build_article(title: str, url: str, body: str) -> str:
    title_line = title or "Article"
    return f"# {title_line}\n\nSource: {url}\n\n{body.strip()}\n"


def _curl_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    proxy: str | None = None,
) -> str:
    """轻量 GET，失败返回空串，不抛异常。"""
    proxies = None
    if proxy:
        proxies = {"http": proxy, "https": proxy}
    try:
        with requests.get(
            url,
            headers=headers or {},
            timeout=timeout,
            proxies=proxies,
            allow_redirects=True,
            verify=True,
            stream=True,
        ) as r:
            content_length = r.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_CURL_RESPONSE_BYTES:
                return ""

            chunks: list[bytes] = []
            total = 0
            for chunk in r.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_CURL_RESPONSE_BYTES:
                    return ""
                chunks.append(chunk)

            encoding = r.encoding or "utf-8"
            return b"".join(chunks).decode(encoding, errors="replace")
    except (OSError, ValueError, requests.RequestException):
        return ""


def _try_payload(url: str, html: str, *, strategy: str, bypassed: bool) -> FetchResult | None:
    """尝试从 HTML 中提取 JSON-LD article 或纯文本，满足条件则返回 FetchResult。"""
    if not html:
        return None
    article = _extract_jsonld_article(html)
    if article and len(article) > 200:
        title = _extract_title(html)
        return FetchResult(
            success=True,
            content=_build_article(title, url, article),
            title=title,
            strategy_used=strategy,
            paywall_bypassed=bypassed,
        )
    text = _html_to_text(html)
    if _has_content(text) and not _is_paywall(text):
        title = _extract_title(html)
        return FetchResult(
            success=True,
            content=text,
            title=title,
            strategy_used=strategy,
            paywall_bypassed=bypassed,
        )
    return None


# ── L1: 代理服务 ────────────────────────────────────────────────


def _l1_jina(url: str, timeout: int) -> FetchResult | None:
    body = _curl_get(f"https://r.jina.ai/{url}", timeout=timeout)
    if _has_content(body) and not _is_paywall(body):
        return FetchResult(
            success=True,
            content=body,
            title=_extract_md_title(body),
            strategy_used="jina",
            paywall_bypassed=False,
        )
    return None


def _l1_defuddle(url: str, timeout: int) -> FetchResult | None:
    body = _curl_get(f"https://defuddle.md/{url}", timeout=timeout)
    if _has_content(body) and not _is_paywall(body):
        return FetchResult(
            success=True,
            content=body,
            title=_extract_md_title(body),
            strategy_used="defuddle",
            paywall_bypassed=False,
        )
    return None


# ── L2/L3: UA 伪装 ─────────────────────────────────────────────


def _ua_attempt(
    url: str,
    *,
    ua: str,
    referer: str,
    extra_headers: dict[str, str] | None = None,
    strategy: str,
    timeout: int,
) -> FetchResult | None:
    headers = {
        "User-Agent": ua,
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml",
        # 清空 cookie：requests 默认不带 cookie，已等价
    }
    if extra_headers:
        headers.update(extra_headers)
    html = _curl_get(url, headers=headers, timeout=timeout)
    return _try_payload(url, html, strategy=strategy, bypassed=True)


def _l2_googlebot(url: str, timeout: int) -> FetchResult | None:
    return _ua_attempt(
        url,
        ua=GOOGLEBOT_UA,
        referer="https://www.google.com/",
        extra_headers={"X-Forwarded-For": "66.249.66.1"},
        strategy="googlebot",
        timeout=timeout,
    )


def _l2_bingbot(url: str, timeout: int) -> FetchResult | None:
    return _ua_attempt(
        url,
        ua=BINGBOT_UA,
        referer="https://www.bing.com/",
        strategy="bingbot",
        timeout=timeout,
    )


def _l3_facebook_ref(url: str, timeout: int) -> FetchResult | None:
    return _ua_attempt(
        url,
        ua=CHROME_UA,
        referer="https://www.facebook.com/",
        strategy="facebook_ref",
        timeout=timeout,
    )


def _l3_twitter_ref(url: str, timeout: int) -> FetchResult | None:
    return _ua_attempt(
        url,
        ua=CHROME_UA,
        referer="https://t.co/",
        strategy="twitter_ref",
        timeout=timeout,
    )


# 已知欧洲 ISP 公网段（IANA RIPE NCC 分配的常见 /8）。
# 旧实现 `185.x.x.x` 全段随机会撞上保留段（如 185.0/16），改成从可用 /8 池随机。
_EU_IP_PREFIXES = (5, 31, 37, 46, 62, 77, 78, 80, 85, 87, 88, 89, 91, 92, 93, 94, 109, 176, 178, 188, 193, 195, 213)


def _l3_eu_ip(url: str, timeout: int) -> FetchResult | None:
    eu_ip = (
        f"{random.choice(_EU_IP_PREFIXES)}."
        f"{random.randint(1, 254)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    )
    return _ua_attempt(
        url,
        ua=CHROME_UA,
        referer="https://www.google.com/",
        extra_headers={"X-Forwarded-For": eu_ip},
        strategy="eu_ip",
        timeout=timeout,
    )


def _l3_amp(url: str, timeout: int) -> FetchResult | None:
    candidates = []
    for suffix in ("/amp", "?outputType=amp", ".amp.html", "?amp"):
        if not url.endswith(suffix):
            candidates.append(url + suffix)
    if url.endswith(".html"):
        candidates.append(url[:-5] + ".amp.html")
    if url.endswith("/"):
        candidates.append(url + "amp")

    for amp_url in candidates:
        html = _curl_get(amp_url, timeout=timeout)
        out = _try_payload(amp_url, html, strategy="amp", bypassed=True)
        if out:
            return out
    return None


# ── L4: archive.today ──────────────────────────────────────────


def _l4_archive(url: str, timeout: int) -> FetchResult | None:
    archive_url = ARCHIVE_BASE + url
    html = _curl_get(
        archive_url,
        headers={"User-Agent": CHROME_UA},
        timeout=timeout,
    )
    if not _has_content(html):
        return None
    if _is_captcha(html):
        raise ArchiveCaptcha(archive_url)
    text = _html_to_text(html)
    if _has_content(text):
        return FetchResult(
            success=True,
            content=text,
            strategy_used="archive",
            paywall_bypassed=True,
            extras={"archive_url": archive_url},
        )
    return None


# ── L5: Google Cache ───────────────────────────────────────────


def _l5_google_cache(url: str, timeout: int) -> FetchResult | None:
    cache_url = "https://webcache.googleusercontent.com/search?q=cache:" + quote(url, safe="")
    html = _curl_get(cache_url, headers={"User-Agent": CHROME_UA}, timeout=timeout)
    if not _has_content(html):
        return None
    text = _html_to_text(html)
    if _has_content(text):
        return FetchResult(
            success=True,
            content=text,
            strategy_used="google_cache",
            paywall_bypassed=True,
        )
    return None


# ── L6: agent-fetch（npx）──────────────────────────────────────


def _l6_agent_fetch(url: str, timeout: int) -> FetchResult | None:
    npx = shutil.which("npx")
    if not npx:
        return None
    try:
        proc = subprocess.run(
            [npx, "--yes", "--package", AGENT_FETCH_PACKAGE, "agent-fetch", url, "--json"],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    body = proc.stdout.strip()
    title = ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            title = str(data.get("title") or "")
            content = data.get("content") or data.get("markdown") or data.get("text") or body
            body = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    if not _has_content(body):
        return None
    return FetchResult(
        success=True,
        content=body,
        title=title,
        strategy_used="agent_fetch",
        paywall_bypassed=True,
    )


# ── 主入口 ─────────────────────────────────────────────────────


def fetch_l1_proxy(url: str, *, timeout: int = 25) -> FetchResult | None:
    """只跑 L1 代理服务，供专用 source fallback 复用。"""
    for fn in (_l1_jina, _l1_defuddle):
        out = fn(url, timeout)
        if out:
            return out
    return None


def fetch_url(
    url: str,
    *,
    timeout: int = 25,
    enable_paywall_bypass: bool = True,
) -> FetchResult:
    """按 6 层级联抓取 URL。

    返回 FetchResult。命中 archive.today CAPTCHA 时抛 ArchiveCaptcha。
    """
    # L1
    out = fetch_l1_proxy(url, timeout=timeout)
    if out:
        return out

    if not enable_paywall_bypass:
        return FetchResult(
            success=False,
            strategy_used="failed",
            error="L1 proxies failed and paywall bypass disabled",
        )

    # L2: 域名匹配 → bot UA
    tried_googlebot = False
    tried_bingbot = False
    if is_googlebot_site(url):
        tried_googlebot = True
        out = _l2_googlebot(url, timeout)
        if out:
            return out
    if is_bingbot_site(url):
        tried_bingbot = True
        out = _l2_bingbot(url, timeout)
        if out:
            return out

    # L3: 通用付费墙绕过
    if is_paywall_site(url):
        bot_fallbacks = []
        if not tried_googlebot:
            bot_fallbacks.append(_l2_googlebot)
        if not tried_bingbot:
            bot_fallbacks.append(_l2_bingbot)
        for fn in bot_fallbacks:
            out = fn(url, timeout)
            if out:
                return out
        if is_facebook_ref_site(url):
            out = _l3_facebook_ref(url, timeout)
            if out:
                return out
        out = _l3_twitter_ref(url, timeout)
        if out:
            return out
        if is_amp_site(url):
            out = _l3_amp(url, timeout)
            if out:
                return out
        out = _l3_eu_ip(url, timeout)
        if out:
            return out

    # L4: archive.today（这里不吞 CAPTCHA 异常）
    out = _l4_archive(url, timeout)
    if out:
        return out

    # L5: Google Cache
    out = _l5_google_cache(url, timeout)
    if out:
        return out

    # L6: agent-fetch
    out = _l6_agent_fetch(url, timeout)
    if out:
        return out

    return FetchResult(
        success=False,
        strategy_used="failed",
        error="All 6 layers failed",
    )
