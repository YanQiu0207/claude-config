#!/usr/bin/env python3
"""download-source 技能环境检查。"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent))

from lib import output as out_mod


GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def status(level: str, msg: str) -> bool:
    color = {"ok": GREEN, "warn": YELLOW, "err": RED}.get(level, "")
    icon = {"ok": "OK", "warn": "WARN", "err": "FAIL"}.get(level, "")
    print(f"{color}[{icon}]{NC} {msg}")
    return level == "ok"


def check_python() -> bool:
    v = sys.version_info
    if v >= (3, 9):
        return status("ok", f"Python {v.major}.{v.minor}.{v.micro}")
    return status("err", f"Python {v.major}.{v.minor}.{v.micro}（需要 3.9+）")


def check_module(import_name: str, hint: str = "") -> bool:
    try:
        importlib.import_module(import_name)
        return status("ok", f"Python module: {import_name}")
    except ImportError:
        msg = f"Python module 缺失: {import_name}"
        if hint:
            msg += f"  → {hint}"
        return status("err", msg)


def check_command(cmd: str, version_arg: str = "--version") -> bool:
    p = shutil.which(cmd)
    if not p:
        return status("warn", f"命令未找到: {cmd}")
    try:
        r = subprocess.run([p, version_arg], capture_output=True, text=True, timeout=5)
        ver = (r.stdout or r.stderr).splitlines()[0].strip() if (r.stdout or r.stderr) else ""
        return status("ok", f"{cmd} 已安装 ({ver})")
    except Exception:  # noqa: BLE001
        return status("ok", f"{cmd} 已安装")


def check_url_md() -> bool:
    p = shutil.which("url-md")
    if not p:
        for cand in (
            Path.home() / ".url-md" / "bin" / "url-md.exe",
            Path.home() / ".url-md" / "bin" / "url-md",
        ):
            if cand.exists():
                p = str(cand)
                break
    if not p:
        return status(
            "warn",
            "url-md 未安装（微信抓取主路径将退化到 jina）。"
            " Windows 安装：irm https://raw.githubusercontent.com/Bwkyd/url-md/main/install.ps1 | iex",
        )
    try:
        r = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=5)
        ver = (r.stdout or r.stderr).strip().splitlines()[0]
        return status("ok", f"url-md 已安装 at {p} ({ver})")
    except Exception:  # noqa: BLE001
        return status("ok", f"url-md 已安装 at {p}")


def check_getnote() -> bool:
    api = os.environ.get("GETNOTE_API_KEY")
    cid = os.environ.get("GETNOTE_CLIENT_ID")
    tokens = Path.home() / ".claude" / "skills" / "getnote" / "tokens.json"
    if api and cid and tokens.exists():
        return status("ok", "Get笔记 凭证完整（GETNOTE_API_KEY + GETNOTE_CLIENT_ID + tokens.json）")
    missing = []
    if not api:
        missing.append("GETNOTE_API_KEY")
    if not cid:
        missing.append("GETNOTE_CLIENT_ID")
    if not tokens.exists():
        missing.append(str(tokens))
    return status(
        "warn",
        f"Get笔记 凭证缺失（{', '.join(missing)}）。"
        " 播客转写将自动降级为 yt-dlp 下音频。",
    )


def check_out_base() -> bool:
    base = out_mod.DEFAULT_OUT_BASE
    if base.exists():
        return status("ok", f"输出根目录已存在: {base}")
    try:
        base.mkdir(parents=True, exist_ok=True)
        return status("ok", f"输出根目录已创建: {base}")
    except OSError as e:
        return status("err", f"无法创建输出根目录 {base}: {e}")


def main() -> int:
    print("==== download-source 环境检查 ====")
    results: list[bool] = []
    results.append(check_python())

    print("-- Python 依赖 --")
    results.append(check_module("requests"))
    results.append(check_module("bs4", hint="pip install beautifulsoup4"))
    results.append(check_module("lxml"))
    results.append(check_module("yaml", hint="pip install pyyaml"))
    results.append(check_module("slugify", hint="pip install python-slugify"))
    results.append(check_module("markitdown", hint="pip install 'markitdown[all]'"))
    results.append(check_module("ebooklib", hint="pip install ebooklib"))
    results.append(check_module("yt_dlp", hint="pip install yt-dlp"))

    print("-- 外部命令 --")
    results.append(check_url_md())
    results.append(check_command("yt-dlp"))
    results.append(check_command("ffmpeg"))
    results.append(check_command("npx", "--version"))

    print("-- 凭证 --")
    check_getnote()

    print("-- 输出目录 --")
    results.append(check_out_base())

    failed = sum(1 for r in results if not r)
    print()
    if failed == 0:
        print(f"{GREEN}全部必需检查通过。{NC}")
        return 0
    print(f"{RED}{failed} 项必需检查未通过，请按上方提示修复。{NC}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
