"""交付门：宣布交付前的确定性检查，替代「AI 自述已完成」。

- **任务终态**（`--tasks`）：tasks.md 每个任务的 `状态` 必须是
  完成 / 需人工 / 阻塞；`需人工` 与 `阻塞` 必须附原因
  （状态行内附注，或单独的 `- 原因:` 字段）。
- **spec 已归档**（`--spec`）：`**状态**:` 必须为 `Archived`。
- **工作区干净**（总是检查）：`git status --porcelain` 必须为空——
  代码与归档产物（spec / tasks / ADR / issues）都已提交本地 git。

Fast-Path（无 spec / tasks）只传 `--repo`，仅检查工作区。
非 0 退出即禁止宣布交付；输出应原样贴进交付报告。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_spec
import lint_task_deps

TERMINAL_STATES = {"完成", "需人工", "阻塞"}
NEEDS_REASON = {"需人工", "阻塞"}


def check_tasks(text: str) -> list[str]:
    """所有任务须处于终态；需人工 / 阻塞 须附原因。"""
    try:
        tasks = lint_task_deps.parse_tasks(text)
    except ValueError as error:
        return [f"tasks.md 解析失败：{error}"]
    if not tasks:
        return ["tasks.md 未解析到任何任务（检查 `### 任务 N:` 格式）"]

    errors: list[str] = []
    for tid, info in sorted(tasks.items()):
        value = lint_task_deps.field(info["body"], "状态")
        state = lint_task_deps.parse_state(value)
        if state is None:
            errors.append(f"任务 {tid} 缺少合法的 状态 字段")
        elif state not in TERMINAL_STATES:
            errors.append(
                f"任务 {tid} 状态为 `{state}`，未到终态（完成 / 需人工 / 阻塞）"
            )
        elif state in NEEDS_REASON:
            note = value[len(state):].strip(" \t:：，,()（）-")
            reason = lint_task_deps.field(info["body"], "原因")
            if not note and not reason:
                errors.append(
                    f"任务 {tid} 标 `{state}` 但未附原因"
                    f"（状态行内补说明，或加 `- 原因:` 字段）"
                )
    return errors


def check_spec(text: str) -> list[str]:
    """spec 状态必须为 Archived。"""
    status = lint_spec.parse_status(text)
    if status != "Archived":
        return [f"spec 状态为 `{status or '缺失'}`，交付前应改为 Archived"]
    return []


def check_git_clean(repo: Path) -> list[str]:
    """git 工作区（含未跟踪文件）必须干净。"""
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return [f"git status 执行失败：{result.stderr.strip()}"]
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        shown = "；".join(dirty[:10])
        suffix = f"（共 {len(dirty)} 项）" if len(dirty) > 10 else ""
        return [f"工作区不干净，未提交改动：{shown}{suffix}"]
    return []


def main(argv: list[str]) -> int:
    """Run the delivery gate and report per-check results."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认非 UTF-8，避免中文乱码

    parser = argparse.ArgumentParser(description="交付前确定性门禁")
    parser.add_argument("--tasks", type=Path, help="tasks.md 路径（标准流程必传）")
    parser.add_argument("--spec", type=Path, help="spec.md 路径（标准流程必传）")
    parser.add_argument("--repo", type=Path, default=Path("."), help="git 仓库根，默认当前目录")
    args = parser.parse_args(argv)

    errors: list[str] = []
    checks = 0

    for label, path, checker in (
        ("tasks.md 全部任务处于终态且附原因", args.tasks, check_tasks),
        ("spec 已归档（Archived）", args.spec, check_spec),
    ):
        if path is None:
            continue
        checks += 1
        if not path.is_file():
            print(f"error: 找不到 {path}", file=sys.stderr)
            return 2
        found = checker(path.read_text(encoding="utf-8", errors="replace"))
        errors.extend(found)
        print(("ERROR  " + "；".join(found)) if found else f"PASS   {label}")

    checks += 1
    found = check_git_clean(args.repo)
    errors.extend(found)
    print(("ERROR  " + "；".join(found)) if found else "PASS   工作区干净（代码与归档产物已提交）")

    print(f"\nchecks={checks} | errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
