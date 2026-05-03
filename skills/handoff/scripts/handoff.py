#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

HANDOFF_DIR = Path.home() / ".claude" / "handoffs"


def configure_stdio() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding and sys.stderr.encoding.lower().replace("-", "") != "utf8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def normalize_filename(filename: str) -> str:
    name = filename.strip().replace("\\", "/")
    if not name or name in {".", ".."}:
        raise ValueError("文件名不能为空。")
    if "/" in name:
        raise ValueError("文件名不能包含路径分隔符。")
    if not name.endswith(".md"):
        name += ".md"
    path = Path(name)
    if path.name != name or path.name in {".md", "..md"}:
        raise ValueError("文件名不合法。")
    return name


def handoff_path(filename: str) -> Path:
    name = normalize_filename(filename)
    return HANDOFF_DIR / name


def extract_field(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def command_list(_: argparse.Namespace) -> int:
    print("## 交接文件列表")
    print()

    if not HANDOFF_DIR.exists():
        print("暂无交接文件。")
        print()
        print("存储路径：~/.claude/handoffs/")
        return 0

    files = sorted(HANDOFF_DIR.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        print("暂无交接文件。")
        print()
        print("存储路径：~/.claude/handoffs/")
        return 0

    print("| # | 文件名 | 标题 | 创建时间 | 项目目录 |")
    print("|---|--------|------|----------|----------|")
    for index, path in enumerate(files, 1):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        title = extract_field(text, r"^#\s+交接记录：(.+)$") or extract_field(text, r"^#\s+(.+)$") or "-"
        created_at = extract_field(text, r"^>\s*创建时间：(.+)$") or "-"
        project_dir = extract_field(text, r"^>\s*项目目录：(.+)$") or "-"
        print(f"| {index} | {path.name} | {title} | {created_at} | {project_dir} |")

    print()
    print(f"共 {len(files)} 个文件，存储路径：~/.claude/handoffs/")
    return 0


def command_read(args: argparse.Namespace) -> int:
    try:
        path = handoff_path(args.filename)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    if not path.exists():
        print(f"文件不存在：~/.claude/handoffs/{path.name}")
        return 1

    try:
        sys.stdout.write(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as error:
        print(f"读取失败：{error}", file=sys.stderr)
        return 1
    return 0


def command_del(args: argparse.Namespace) -> int:
    try:
        path = handoff_path(args.filename)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    if not path.exists():
        print(f"文件不存在：~/.claude/handoffs/{path.name}")
        return 1

    if not args.yes:
        print(f"即将删除文件：~/.claude/handoffs/{path.name}")
        print("此操作不可逆，文件内容将永久丢失。")
        print()
        print('请重新执行并添加 --yes 以确认删除。')
        return 2

    try:
        path.unlink()
    except OSError as error:
        print(f"删除失败：{error}", file=sys.stderr)
        return 1

    print(f"已删除：~/.claude/handoffs/{path.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 Claude Code handoff 交接文件。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出所有交接文件。")
    list_parser.set_defaults(func=command_list)

    read_parser = subparsers.add_parser("read", help="读取指定交接文件。")
    read_parser.add_argument("filename")
    read_parser.set_defaults(func=command_read)

    del_parser = subparsers.add_parser("del", help="删除指定交接文件。")
    del_parser.add_argument("filename")
    del_parser.add_argument("--yes", action="store_true", help="确认删除。")
    del_parser.set_defaults(func=command_del)

    return parser


def main() -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
