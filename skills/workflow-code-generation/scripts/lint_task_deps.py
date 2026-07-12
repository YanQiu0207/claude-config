"""Lint tasks.md 的依赖关系，提示并行分波的潜在冲突。

按 task_planning_guide.md 的 tasks.md 格式解析每个任务的 `文件` 与
`depends_on` 字段，检查：

- **dangling 依赖**：`depends_on` 指向不存在的任务号（ERROR）。
- **循环依赖**：依赖图存在环，违反 DAG 约定（ERROR）。
- **并行冲突**：两个任务改同一文件、却无依赖关系——会被分到同一波并行执行，
  worktree 合并时冲突或顺序错（WARN，提示确认是否补 `depends_on`）。
- **必填字段**：每个任务须有 `review_profile`（lightweight / standard / strict）、
  `context_files`、`verification`、`artifacts`、`状态`（合法值），缺失或非法（ERROR）。

只查「文件重叠 + 无依赖」这一客观信号；是否真要串行由人判断（重叠可能是有意且已处理）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TASK_HEADER = re.compile(r"^###\s*任务\s*(\d+)\s*[:：]", re.MULTILINE)
BACKTICK = re.compile(r"`([^`]+)`")

REVIEW_PROFILES = {"lightweight", "standard", "strict"}
TASK_STATES = ("未开始", "进行中", "完成", "需人工", "阻塞")
REQUIRED_FIELDS = ("review_profile", "context_files", "verification", "artifacts", "状态")


def field(body: str, name: str) -> str:
    """取 `- <name>: <值>` 那一行的值，找不到返回空串。"""
    match = re.search(r"^\s*-\s*" + name + r"\s*[:：]\s*(.*)$", body, re.MULTILINE)
    return match.group(1).strip() if match else ""


def has_field(body: str, name: str) -> bool:
    """Return whether a task field is declared, even when its value is empty."""
    return re.search(
        r"^\s*-\s*" + name + r"\s*[:：]", body, re.MULTILINE
    ) is not None


def parse_deps(body: str) -> tuple[set[int], bool]:
    """解析 depends_on，兼容旧字段 `依赖`，并返回字段是否存在。"""
    has_depends_on = has_field(body, "depends_on")
    has_legacy_dep = has_field(body, "依赖")
    dep_text = field(body, "depends_on")
    if not has_depends_on:
        dep_text = field(body, "依赖")
    field_exists = has_depends_on or has_legacy_dep
    if not dep_text or dep_text in {"[]", "无"}:
        return set(), field_exists
    return {int(n) for n in re.findall(r"\d+", dep_text)}, field_exists


def parse_tasks(text: str) -> dict[int, dict]:
    """解析 tasks.md，返回 {task_id: {"files": set, "deps": set}}。"""
    headers = list(TASK_HEADER.finditer(text))
    tasks: dict[int, dict] = {}
    for idx, match in enumerate(headers):
        tid = int(match.group(1))
        if tid in tasks:
            raise ValueError(f"重复任务 ID: {tid}")
        start = match.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        body = text[start:end]

        files = {p.strip() for p in BACKTICK.findall(field(body, "文件"))}
        deps, has_dep_field = parse_deps(body)
        tasks[tid] = {
            "files": files,
            "deps": deps,
            "has_dep_field": has_dep_field,
            "body": body,
        }
    return tasks


def parse_state(value: str) -> str | None:
    """从 `状态` 字段值里取合法状态词（允许后跟原因等附注），无则返回 None。"""
    for state in TASK_STATES:
        if value.startswith(state):
            return state
    return None


def field_errors(tasks: dict[int, dict]) -> list[str]:
    """校验每个任务的必填字段与合法值。"""
    errors: list[str] = []
    for tid, info in sorted(tasks.items()):
        body = info["body"]
        for name in REQUIRED_FIELDS:
            if not has_field(body, name):
                errors.append(f"任务 {tid} 缺少 {name} 字段")
        if has_field(body, "review_profile"):
            profile = field(body, "review_profile")
            if profile not in REVIEW_PROFILES:
                errors.append(
                    f"任务 {tid} 的 review_profile `{profile}` 不合法"
                    f"（lightweight / standard / strict）"
                )
        if has_field(body, "状态"):
            status_value = field(body, "状态")
            if parse_state(status_value) is None:
                errors.append(
                    f"任务 {tid} 的 状态 `{status_value}` 不含合法值"
                    f"（{' / '.join(TASK_STATES)}）"
                )
    return errors


def reachable(tasks: dict[int, dict]) -> dict[int, set[int]]:
    """每个任务经依赖可达的任务集合（传递闭包）。

    每个源点独立做一次 DFS（不跨源点 memo），即使存在环也能算出完整可达集，
    从而把环里的每个成员都标出来。
    """
    reach: dict[int, set[int]] = {}
    for tid in tasks:
        seen: set[int] = set()
        stack = [d for d in tasks[tid]["deps"] if d in tasks]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(d for d in tasks[node]["deps"] if d in tasks)
        reach[tid] = seen
    return reach


def main(argv: list[str]) -> int:
    """解析 tasks.md 并报告依赖问题。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台避免中文乱码

    parser = argparse.ArgumentParser(description="校验 tasks.md 的依赖关系")
    parser.add_argument("tasks_md", type=Path, help="tasks.md 路径")
    args = parser.parse_args(argv)
    if not args.tasks_md.is_file():
        print(f"error: 找不到 {args.tasks_md}", file=sys.stderr)
        return 2

    try:
        tasks = parse_tasks(
            args.tasks_md.read_text(encoding="utf-8-sig", errors="replace")
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if not tasks:
        print("error: 未解析到任何任务（检查 tasks.md 是否符合 `### 任务 N:` 格式）", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    # dangling 依赖
    for tid, info in sorted(tasks.items()):
        if not info["has_dep_field"]:
            errors.append(f"任务 {tid} 缺少 depends_on 字段")
        for dep in sorted(info["deps"]):
            if dep not in tasks:
                errors.append(f"任务 {tid} 依赖不存在的任务 {dep}")

    # 必填字段与合法值
    errors.extend(field_errors(tasks))

    reach = reachable(tasks)

    # 循环依赖
    for tid in sorted(tasks):
        if tid in reach[tid]:
            errors.append(f"任务 {tid} 存在循环依赖（依赖链回到自身）")

    # 并行冲突：文件重叠但互不可达
    ids = sorted(tasks)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            shared = tasks[a]["files"] & tasks[b]["files"]
            if not shared:
                continue
            if b in reach[a] or a in reach[b]:
                continue  # 有依赖关系 → 串行，安全
            files = "、".join(f"`{f}`" for f in sorted(shared))
            warnings.append(
                f"任务 {a} 与 任务 {b} 都改 {files}，但无依赖关系（会并行）"
                f"→ 确认是否需要加 depends_on"
            )

    for message in errors:
        print(f"ERROR  {message}")
    for message in warnings:
        print(f"WARN   {message}")
    print(f"\ntasks={len(tasks)} | errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors or warnings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
