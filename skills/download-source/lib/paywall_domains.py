"""付费墙站点域名清单（移植自 Bypass-Paywalls-Clean，原 fetch_url.sh）。

来源：
- 原项目 scripts/fetch_url.sh
  https://github.com/joeseesun/qiaomu-anything-to-notebooklm/blob/main/scripts/fetch_url.sh
- BPC 上游
  https://gitflic.ru/project/magnolia1234/bpc_uploads
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Googlebot UA 能拿到完整正文（SEO 白名单）的站点
GOOGLEBOT_DOMAINS = (
    "wsj.com|barrons.com|ft.com|economist.com|theaustralian.com.au|"
    "thetimes.co.uk|telegraph.co.uk|zeit.de|handelsblatt.com|leparisien.fr|"
    "nzz.ch|usatoday.com|quora.com|lefigaro.fr|lemonde.fr|spiegel.de|"
    "sueddeutsche.de|frankfurter-allgemeine.de|wires.com|"
    "brisbanetimes.com.au|smh.com.au|theage.com.au"
)

# Bingbot UA 有效的站点
BINGBOT_DOMAINS = "haaretz.com|nzherald.co.nz|stratfor.com|themarker.com"

# 接受社交流量（Facebook Referer）的站点
FACEBOOK_REF_DOMAINS = "law.com|ftm.nl|law360.com|sloanreview.mit.edu"

# 提供 AMP 页面且付费墙较弱的站点
AMP_DOMAINS = (
    "wsj.com|bostonglobe.com|latimes.com|chicagotribune.com|seattletimes.com|"
    "theatlantic.com|wired.com|newyorker.com|washingtonpost.com|smh.com.au|"
    "theage.com.au|brisbanetimes.com.au"
)

# 通用付费墙域名清单（用于触发 L3 通用绕过）
PAYWALL_DOMAINS = (
    "nytimes.com|wsj.com|ft.com|economist.com|bloomberg.com|"
    "washingtonpost.com|newyorker.com|wired.com|theatlantic.com|medium.com|"
    "businessinsider.com|technologyreview.com|scmp.com|seattletimes.com|"
    "bostonglobe.com|latimes.com|chicagotribune.com|theglobeandmail.com|"
    "afr.com|thetimes.co.uk|telegraph.co.uk|spiegel.de|zeit.de|"
    "sueddeutsche.de|barrons.com|forbes.com|foreignaffairs.com|"
    "foreignpolicy.com|harvard.edu|newscientist.com|scientificamerican.com|"
    "theinformation.com|statista.com|handelsblatt.com|nzz.ch|"
    "leparisien.fr|lefigaro.fr|lemonde.fr|haaretz.com|nzherald.co.nz|"
    "theaustralian.com.au|smh.com.au|theage.com.au|quora.com|usatoday.com"
)


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_GOOGLEBOT_RE = _compile(GOOGLEBOT_DOMAINS)
_BINGBOT_RE = _compile(BINGBOT_DOMAINS)
_FACEBOOK_REF_RE = _compile(FACEBOOK_REF_DOMAINS)
_AMP_RE = _compile(AMP_DOMAINS)
_PAYWALL_RE = _compile(PAYWALL_DOMAINS)


def _host(url: str) -> str:
    """从 URL 提 host，避免对路径/query 做匹配（否则 `?ref=quora.com` 会误命中）。"""
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def is_googlebot_site(url: str) -> bool:
    return bool(_GOOGLEBOT_RE.search(_host(url)))


def is_bingbot_site(url: str) -> bool:
    return bool(_BINGBOT_RE.search(_host(url)))


def is_facebook_ref_site(url: str) -> bool:
    return bool(_FACEBOOK_REF_RE.search(_host(url)))


def is_amp_site(url: str) -> bool:
    return bool(_AMP_RE.search(_host(url)))


def is_paywall_site(url: str) -> bool:
    return bool(_PAYWALL_RE.search(_host(url)))
