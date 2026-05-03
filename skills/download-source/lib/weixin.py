"""微信公众号文章抓取（url-md 优先，jina fallback）。

策略：

  L1  url-md md <url> -o <out_dir>   （主路径，自动下载图片到 out_dir/assets/）
       url-md 是 Bwkyd 的 Rust 单二进制（7 MB，无 Chrome 依赖）：
         https://github.com/Bwkyd/url-md
       v0.3.0 起作为 wexin-read-mcp 的内部抓取层，微信永久链走 reqwest。
       Windows 安装：irm https://raw.githubusercontent.com/Bwkyd/url-md/main/install.ps1 | iex

  L2  fetch_url 的 L1（jina/defuddle）兜底
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .fetch_url import fetch_l1_proxy


@dataclass
class WeixinResult:
    success: bool
    title: str = ""
    author: str = ""
    publish_time: str = ""
    cover_url: str = ""
    content_md: str = ""
    strategy_used: str = ""
    files: list[str] = field(default_factory=list)
    error: str = ""


URL_MD_EXIT_HINTS = {
    10: "network error",
    11: "blocked by anti-bot",
    12: "paywalled",
    13: "auth required",
    20: "parse/extract failed",
    30: "I/O error",
    99: "internal error",
}


def _resolve_url_md_bin() -> str | None:
    """找 url-md 可执行文件。

    Windows 装到 %USERPROFILE%\\.url-md\\bin\\url-md.exe，可能未加 PATH。
    """
    p = shutil.which("url-md")
    if p:
        return p
    # Windows 常见安装位置
    home = Path.home()
    for cand in (
        home / ".url-md" / "bin" / "url-md.exe",
        home / ".url-md" / "bin" / "url-md",
    ):
        if cand.exists():
            return str(cand)
    return None


def _explain_exit(code: int, stderr: str) -> str:
    hint = URL_MD_EXIT_HINTS.get(code, f"exit code {code}")
    stderr = stderr.strip()
    return f"url-md failed ({hint}): {stderr}" if stderr else f"url-md failed ({hint})"


def fetch_weixin_with_urlmd(
    url: str,
    out_dir: Path,
    timeout: int = 45,
) -> WeixinResult:
    """调 url-md md <url> -o <out_dir> 抓取微信文章并下载图片到 out_dir/assets/。

    输出文件：
      <out_dir>/index.md     # url-md 默认输出名（含 YAML frontmatter）
      <out_dir>/assets/*     # 图片
    """
    bin_path = _resolve_url_md_bin()
    if not bin_path:
        return WeixinResult(
            success=False,
            strategy_used="url_md_missing",
            error=(
                "url-md binary not found. Install on Windows:\n"
                "  irm https://raw.githubusercontent.com/Bwkyd/url-md/main/install.ps1 | iex\n"
                "Or macOS/Linux:\n"
                "  curl -fsSL https://raw.githubusercontent.com/Bwkyd/url-md/main/install.sh | bash"
            ),
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    # 记录调用前已存在的 .md，url-md 跑完后只取「新增」的，避免误中残留文件
    md_before = {p.resolve() for p in out_dir.glob("*.md") if p.is_file()}

    try:
        proc = subprocess.run(
            [
                bin_path,
                "md",
                url,
                "-o",
                str(out_dir),
                "--quiet",
                "--timeout",
                str(timeout),
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return WeixinResult(
            success=False,
            strategy_used="url_md_timeout",
            error=f"url-md subprocess timeout after {timeout}s",
        )
    except OSError as e:
        return WeixinResult(
            success=False,
            strategy_used="url_md_oserror",
            error=f"url-md OSError: {e}",
        )

    if proc.returncode != 0:
        return WeixinResult(
            success=False,
            strategy_used="url_md_failed",
            error=_explain_exit(proc.returncode, proc.stderr or ""),
        )

    # url-md `-o <dir>` 模式下自动命名为 `{date}-{host}-{slug}.md`，
    # 文件名不固定。比较调用前后的 .md 集合，只取「新增」的，避免拾取
    # fallback 路径之前留下的 content.md 等残留文件。
    md_text = ""
    md_file: Path | None = None
    md_after = {p.resolve() for p in out_dir.glob("*.md") if p.is_file()}
    new_mds = sorted(md_after - md_before, key=lambda p: p.name)
    if new_mds:
        md_file = new_mds[0]
        md_text = md_file.read_text(encoding="utf-8", errors="replace")
    elif proc.stdout:
        md_file = out_dir / "content.md"
        md_text = proc.stdout
        md_file.write_text(md_text, encoding="utf-8")

    if not md_text:
        return WeixinResult(
            success=False,
            strategy_used="url_md_empty",
            error="url-md returned empty output",
        )

    parsed = _parse_urlmd_markdown(md_text)
    files = [str(md_file)]
    assets_dir = out_dir / "assets"
    if assets_dir.exists():
        for f in sorted(assets_dir.iterdir()):
            if f.is_file():
                files.append(str(f))

    return WeixinResult(
        success=True,
        title=parsed.get("title") or "",
        author=parsed.get("author") or "",
        publish_time=parsed.get("publish_time") or "",
        cover_url=parsed.get("cover_url") or "",
        content_md=parsed.get("body") or md_text,
        strategy_used="url_md",
        files=files,
    )


def _parse_urlmd_markdown(md: str) -> dict[str, Any]:
    """从 url-md 输出解析 YAML frontmatter + body。

    格式：
      ---
      title: ...
      author: ...
      publish_time: ...
      cover_url: ...
      ---
      <body>
    """
    # 归一化换行后再处理，避免 CRLF/LF 混合时分隔符匹配失败导致 frontmatter 整段沉到 body
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    if not md.startswith("---\n"):
        return {"body": md.strip()}
    parts = md.split("---\n", 2)
    if len(parts) < 3:
        return {"body": md.strip()}
    try:
        fm = yaml.safe_load(parts[1]) or {}
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}
    return {
        "title": str(fm.get("title") or ""),
        "author": str(fm.get("author") or ""),
        "publish_time": str(fm.get("publish_time") or ""),
        "cover_url": str(fm.get("cover_url") or ""),
        "body": parts[2].lstrip("\n\r"),
    }


def fetch_weixin_via_jina(url: str, timeout: int = 25) -> WeixinResult:
    """url-md 失败时的 fallback：直接调 fetch_url 的 L1 代理服务。

    defuddle 输出本身带 YAML frontmatter（title/author/site/source/...），
    解析后回填到 WeixinResult 各字段；jina 只有 `Title:` 伪 frontmatter
    （L1 jina 已通过 `_extract_md_title` 处理 title），其余字段保持空。
    """
    out = fetch_l1_proxy(url, timeout=timeout)
    if out is None or not out.success:
        return WeixinResult(
            success=False,
            strategy_used="weixin_fallback_failed",
            error="Both jina and defuddle failed for weixin URL",
        )

    parsed = _parse_urlmd_markdown(out.content)
    return WeixinResult(
        success=True,
        title=parsed.get("title") or out.title or "",
        author=parsed.get("author") or "",
        publish_time=parsed.get("publish_time") or "",
        cover_url=parsed.get("cover_url") or "",
        content_md=out.content,
        strategy_used=out.strategy_used,
    )


def fetch_weixin(url: str, out_dir: Path, timeout: int = 45) -> WeixinResult:
    """主入口：先 url-md，失败 fallback jina/defuddle。"""
    primary = fetch_weixin_with_urlmd(url, out_dir, timeout)
    if primary.success:
        return primary
    fb = fetch_weixin_via_jina(url, min(timeout, 25))
    if fb.success:
        # 写 fallback 的 markdown 到 out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        md_file = out_dir / "content.md"
        md_file.write_text(fb.content_md, encoding="utf-8")
        fb.files = [str(md_file)]
        return fb
    # 都失败
    return WeixinResult(
        success=False,
        strategy_used="weixin_all_failed",
        error=f"url-md: {primary.error} | fallback: {fb.error}",
    )
