"""Lint spec.md 的章节完整性（设计 / 编码前的确定性门禁）。

按 spec 的 `状态` 与 `--phase` 校验章节完整性，替代「AI 自述已写好」：

- **状态字段**：必须从模板占位中选定单一合法值
  （Draft / In Review / Approved / Archived / Quick Draft）。
- **标准 spec**：`--phase design` 要求 1~3 章、`--phase code` 要求 1~4 章
  存在且有实质内容；不适用的章节必须显式标 `N/A`。
- **Quick Draft**：要求 问题 / 目标 / 整体方案 / 验收标准 四节有实质内容。

「实质内容」判定：对照生成用模板（默认随框架仓库定位，可用 `--template` 覆盖），
与模板逐行相同的内容视为占位——连「复制模板未填写」也会被拦下；
找不到模板时退化为启发式（存在非 TODO 的正文行）并给 WARN。

只判「章节存在 + 非占位」，不判内容质量——那是 review 的职责。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 本脚本位于 <skills>/workflow-code-generation/scripts/，模板按兄弟 skill 定位；
# 框架仓库与安装后的 .claude/.codex skills 目录布局一致，两处均可解析。
SKILLS_ROOT = Path(__file__).resolve().parents[2]
STANDARD_TEMPLATE = (
    SKILLS_ROOT / "workflow-requirements-clarification" / "reference" / "spec_template.md"
)
QUICK_TEMPLATE = (
    SKILLS_ROOT / "workflow-quick-design" / "reference" / "quick-spec-template.md"
)

STATUSES = {"Draft", "In Review", "Approved", "Archived", "Quick Draft"}
STATUS_RE = re.compile(r"^\*\*状态\*\*\s*[:：]\s*(.+?)\s*$", re.MULTILINE)
CHAPTER_RE = re.compile(r"^##\s*(\d+)(?:[.、]|\s)\s*(.*)$")
SUBSECTION_RE = re.compile(r"^###\s+(.+?)\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# 单独成行的占位词不算实质内容
PLACEHOLDER_RE = re.compile(r"^(?:todo|tbd|xxx|待补充|待填写|待定)$", re.IGNORECASE)

PHASE_CHAPTERS = {"design": (1, 2, 3), "code": (1, 2, 3, 4)}
QUICK_SECTIONS = ("问题", "目标", "整体方案", "验收标准")


def read(path: Path) -> str:
    """Read a file as UTF-8, tolerating stray bytes."""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_status(text: str) -> str | None:
    """取 `**状态**: <值>` 的值，找不到返回 None。"""
    match = STATUS_RE.search(text)
    return match.group(1).strip() if match else None


def chapter_bodies(text: str) -> dict[int, str]:
    """按 `## N.` 切分正文，返回 {章节号: 正文（不含本章标题行）}。"""
    chapters: dict[int, str] = {}
    current: int | None = None
    lines: list[str] = []
    for line in text.splitlines():
        match = CHAPTER_RE.match(line)
        if match:
            if current is not None:
                chapters[current] = "\n".join(lines)
            current = int(match.group(1))
            lines = []
        elif line.startswith("## "):  # 无编号的 ## 标题结束上一章
            if current is not None:
                chapters[current] = "\n".join(lines)
            current = None
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None:
        chapters[current] = "\n".join(lines)
    return chapters


def normalize_heading(title: str) -> str:
    """去掉编号与括注，如 `2.1 整体方案` → `整体方案`、`数据模型（如适用）` → `数据模型`。"""
    title = re.sub(r"^[\d.、\s]+", "", title)
    title = re.sub(r"[（(].*?[)）]\s*$", "", title)
    return title.strip()


def quick_section_bodies(text: str) -> dict[str, str]:
    """按 `###` 切分，返回 {规范化标题: 正文}。同名小节以首个为准。"""
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        match = SUBSECTION_RE.match(line)
        if match:
            if current is not None and current not in sections:
                sections[current] = "\n".join(lines)
            current = normalize_heading(match.group(1))
            lines = []
        elif line.startswith("## "):
            if current is not None and current not in sections:
                sections[current] = "\n".join(lines)
            current = None
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None and current not in sections:
        sections[current] = "\n".join(lines)
    return sections


def template_lines(template_text: str) -> set[str]:
    """模板全部非空行（strip 后），用于占位对照。"""
    return {
        line.strip()
        for line in COMMENT_RE.sub("", template_text).splitlines()
        if line.strip()
    }


def has_substance(body: str, template: set[str] | None) -> bool:
    """正文是否含实质内容：跳过标题 / 空行 / 空 bullet / 模板占位 / TODO 类占位词。"""
    for line in COMMENT_RE.sub("", body).splitlines():
        stripped = line.strip()
        if not stripped or HEADING_RE.match(line) or stripped in {"-", "*"}:
            continue
        if template is not None and stripped in template:
            continue
        if PLACEHOLDER_RE.match(stripped.strip("-* ").strip()):
            continue
        return True
    return False


def lint(text: str, phase: str, template_text: str | None) -> list[str]:
    """返回 ERROR 列表。状态非法 / 章节缺失 / 章节仅有占位均报错。"""
    errors: list[str] = []
    template = template_lines(template_text) if template_text is not None else None

    status = parse_status(text)
    if status is None:
        errors.append("缺少 `**状态**:` 字段")
    elif status not in STATUSES:
        hint = "（未从模板占位中选定单一状态）" if "/" in status else ""
        errors.append(f"状态 `{status}` 不合法{hint}，合法值：{' / '.join(sorted(STATUSES))}")

    if status == "Quick Draft":
        sections = quick_section_bodies(text)
        for name in QUICK_SECTIONS:
            if name not in sections:
                errors.append(f"缺少「{name}」小节（### {name}）")
            elif not has_substance(sections[name], template):
                errors.append(f"「{name}」小节仅有模板占位，未填写实质内容")
        return errors

    chapters = chapter_bodies(text)
    for number in PHASE_CHAPTERS[phase]:
        if number not in chapters:
            errors.append(f"缺少第 {number} 章（`## {number}.`）")
        elif not has_substance(chapters[number], template):
            errors.append(
                f"第 {number} 章仅有模板占位，未填写实质内容（不适用请显式标 N/A）"
            )
    return errors


def main(argv: list[str]) -> int:
    """Run the linter and report errors / warnings."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认非 UTF-8，避免中文乱码

    parser = argparse.ArgumentParser(description="校验 spec.md 章节完整性")
    parser.add_argument("spec_md", type=Path, help="spec.md 路径")
    parser.add_argument(
        "--phase",
        choices=("design", "code"),
        default="code",
        help="design：设计前查 1~3 章；code（默认）：编码前查 1~4 章。Quick Draft 忽略此项。",
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="占位对照模板路径；默认按状态取框架内置模板",
    )
    args = parser.parse_args(argv)
    if not args.spec_md.is_file():
        print(f"error: 找不到 {args.spec_md}", file=sys.stderr)
        return 2

    text = read(args.spec_md)
    status = parse_status(text)

    warnings: list[str] = []
    template_path = args.template or (
        QUICK_TEMPLATE if status == "Quick Draft" else STANDARD_TEMPLATE
    )
    template_text: str | None = None
    if template_path.is_file():
        template_text = read(template_path)
    else:
        warnings.append(f"模板 {template_path} 未找到，占位判定退化为启发式")

    errors = lint(text, args.phase, template_text)

    for message in errors:
        print(f"ERROR  {message}")
    for message in warnings:
        print(f"WARN   {message}")
    print(
        f"\nspec={args.spec_md} phase={args.phase} status={status or '缺失'} "
        f"| errors={len(errors)} warnings={len(warnings)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
