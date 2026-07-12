"""Deterministic control-flow decisions for workflow tasks."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import lint_task_deps


@dataclass(frozen=True)
class TaskDecision:
    """A validated task transition decision."""

    task_id: int
    state: str
    action: str
    reason: str = ""
    attempts: int = 0
    control_stage: str = ""


@dataclass(frozen=True)
class RecoveryAction:
    """An action required to recover one task after interruption."""

    task_id: int
    action: str
    reason: str = ""


def _states(tasks: dict[int, dict]) -> dict[int, str]:
    states = {}
    for task_id, task in tasks.items():
        state = lint_task_deps.parse_state(
            lint_task_deps.field(task["body"], "状态")
        )
        if state is None:
            raise ValueError(f"任务 {task_id} 缺少合法状态")
        states[task_id] = state
    return states


def _attempts(task: dict) -> int:
    value = lint_task_deps.field(task["body"], "attempts")
    if not value:
        return 0
    if not value.isdigit():
        raise ValueError(f"非法 attempts: {value}")
    return int(value)


def _control_stage(task: dict, state: str) -> str:
    value = lint_task_deps.field(task["body"], "control_stage")
    if value:
        return value
    return {
        "未开始": "pending",
        "进行中": "running",
        "完成": "completed",
        "需人工": "manual",
        "阻塞": "blocked",
    }[state]


def _validate_dependencies(tasks: dict[int, dict]) -> None:
    for task_id, task in tasks.items():
        if not task["has_dep_field"]:
            raise ValueError(f"任务 {task_id} 缺少 depends_on 字段")
        missing = task["deps"] - tasks.keys()
        if missing:
            raise ValueError(f"任务 {task_id} 依赖不存在的任务 {min(missing)}")


def _validate_reason(reason: str) -> None:
    if "\r" in reason or "\n" in reason:
        raise ValueError("原因不能包含换行符")


def build_waves(tasks: dict[int, dict]) -> list[list[int]]:
    """Build stable topological waves from parsed tasks."""
    _validate_dependencies(tasks)
    remaining = set(tasks)
    completed: set[int] = set()
    waves = []
    while remaining:
        wave = sorted(
            task_id
            for task_id in remaining
            if tasks[task_id]["deps"] <= completed
        )
        if not wave:
            raise ValueError("任务依赖存在循环")
        waves.append(wave)
        completed.update(wave)
        remaining.difference_update(wave)
    return waves


def dispatchable_tasks(tasks: dict[int, dict]) -> list[int]:
    """Return pending tasks whose dependencies are complete."""
    _validate_dependencies(tasks)
    states = _states(tasks)
    return [
        task_id
        for task_id in sorted(tasks)
        if states[task_id] == "未开始"
        and all(
            states[dependency] == "完成"
            for dependency in tasks[task_id]["deps"]
        )
    ]


def apply_event(
    tasks: dict[int, dict],
    task_id: int,
    event: str,
    reason: str = "",
    max_attempts: int = 2,
) -> TaskDecision:
    """Validate one orchestration event against persisted task state."""
    if task_id not in tasks:
        raise ValueError(f"找不到任务 {task_id}")
    _validate_dependencies(tasks)
    if max_attempts < 0:
        raise ValueError("最大修复次数不能为负数")
    _validate_reason(reason)
    state = _states(tasks)[task_id]
    attempts = _attempts(tasks[task_id])
    stage = _control_stage(tasks[task_id], state)
    if (state, stage, event) not in {
        ("未开始", "pending", "start"),
        ("进行中", "running", "failure"),
        ("进行中", "running", "quality_passed"),
        ("进行中", "quality_passed", "merge_success"),
        ("进行中", "quality_passed", "merge_failure"),
        ("阻塞", "blocked", "unblock"),
    }:
        raise ValueError(
            f"任务 {task_id} 不允许从 {state}/{stage} 执行 {event}"
        )
    if event == "start":
        states = _states(tasks)
        if any(
            states[dependency] != "完成"
            for dependency in tasks[task_id]["deps"]
        ):
            raise ValueError(f"任务 {task_id} 的前置依赖尚未全部完成")
        return TaskDecision(
            task_id, "进行中", "dispatch", reason, attempts, "running"
        )
    if event == "quality_passed":
        return TaskDecision(
            task_id,
            "进行中",
            "merge",
            reason,
            attempts,
            "quality_passed",
        )
    if event == "merge_success":
        return TaskDecision(
            task_id, "完成", "complete", reason, attempts, "completed"
        )
    if event == "merge_failure":
        return TaskDecision(
            task_id, "需人工", "manual", reason, attempts, "manual"
        )
    if event == "unblock":
        states = _states(tasks)
        if any(
            states[dependency] != "完成"
            for dependency in tasks[task_id]["deps"]
        ):
            raise ValueError(f"任务 {task_id} 的前置依赖尚未全部完成")
        return TaskDecision(
            task_id, "未开始", "unblock", reason, attempts, "pending"
        )

    attempts += 1
    if attempts <= max_attempts:
        return TaskDecision(
            task_id, "进行中", "retry", reason, attempts, "running"
        )
    exhausted = reason or f"修复次数已耗尽（{attempts - 1}/{max_attempts}）"
    return TaskDecision(
        task_id, "需人工", "manual", exhausted, attempts, "manual"
    )


def propagate_blocked(tasks: dict[int, dict]) -> list[TaskDecision]:
    """Return decisions that recursively block descendants of failed tasks."""
    _validate_dependencies(tasks)
    states = _states(tasks)
    decisions = []
    changed = True
    while changed:
        changed = False
        for task_id in sorted(tasks):
            if states[task_id] in {"完成", "需人工", "阻塞"}:
                continue
            blockers = sorted(
                dependency
                for dependency in tasks[task_id]["deps"]
                if states[dependency] in {"需人工", "阻塞"}
            )
            if not blockers:
                continue
            states[task_id] = "阻塞"
            decisions.append(
                TaskDecision(
                    task_id,
                    "阻塞",
                    "block",
                    f"上游 Task {blockers[0]} 未合并",
                    _attempts(tasks[task_id]),
                    "blocked",
                )
            )
            changed = True
    return decisions


def plan_recovery(
    tasks: dict[int, dict], merged_task_ids: set[int]
) -> list[RecoveryAction]:
    """Plan recovery using task state and externally supplied merge facts."""
    _validate_dependencies(tasks)
    unknown = merged_task_ids - tasks.keys()
    if unknown:
        raise ValueError(f"已合并集合包含未知任务 {min(unknown)}")
    states = _states(tasks)
    effective = {**states, **{task_id: "完成" for task_id in merged_task_ids}}
    actions = []
    for task_id in sorted(tasks):
        state = states[task_id]
        deps_complete = all(
            effective[dependency] == "完成"
            for dependency in tasks[task_id]["deps"]
        )
        if state == "完成":
            action = RecoveryAction(task_id, "skip", "任务已完成")
        elif state == "进行中" and task_id in merged_task_ids:
            action = RecoveryAction(task_id, "complete", "任务分支已合并")
        elif state == "进行中":
            action = RecoveryAction(
                task_id, "inspect", "任务未合并，检查产物和质量门"
            )
        elif state == "阻塞" and deps_complete:
            action = RecoveryAction(task_id, "unblock", "全部上游已完成")
        elif state == "未开始" and deps_complete:
            action = RecoveryAction(task_id, "dispatch", "前置依赖已完成")
        else:
            action = RecoveryAction(task_id, "wait", "前置依赖未完成")
        actions.append(action)
    return actions


def _task_bounds(text: str, task_id: int) -> tuple[int, int]:
    headers = list(lint_task_deps.TASK_HEADER.finditer(text))
    index = next(
        (
            index
            for index, header in enumerate(headers)
            if int(header.group(1)) == task_id
        ),
        None,
    )
    if index is None:
        raise ValueError(f"找不到任务 {task_id}")
    start = headers[index].end()
    end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
    return start, end


def update_task_state(text: str, decision: TaskDecision) -> str:
    """Precisely persist one validated decision without reserializing Markdown."""
    _validate_reason(decision.reason)
    start, end = _task_bounds(text, decision.task_id)
    body = text[start:end]
    newline = "\r\n" if "\r\n" in text else "\n"
    pattern = re.compile(r"^[ \t]*-[ \t]*状态[ \t]*[:：][^\r\n]*", re.MULTILINE)
    if not pattern.search(body):
        raise ValueError(f"任务 {decision.task_id} 缺少状态字段")
    replacement = f"- 状态：{decision.state}"
    if decision.reason:
        replacement += f"（{decision.reason}）"
    body = pattern.sub(replacement, body, count=1)
    attempts_pattern = re.compile(
        r"^[ \t]*-[ \t]*attempts[ \t]*[:：][^\r\n]*", re.MULTILINE
    )
    attempts_line = f"- attempts：{decision.attempts}"
    if attempts_pattern.search(body):
        body = attempts_pattern.sub(attempts_line, body, count=1)
    else:
        body = pattern.sub(
            lambda match: f"{match.group(0)}{newline}{attempts_line}",
            body,
            count=1,
        )
    stage_pattern = re.compile(
        r"^[ \t]*-[ \t]*control_stage[ \t]*[:：][^\r\n]*", re.MULTILINE
    )
    stage_line = f"- control_stage：{decision.control_stage}"
    if stage_pattern.search(body):
        body = stage_pattern.sub(stage_line, body, count=1)
    else:
        body = attempts_pattern.sub(
            lambda match: f"{match.group(0)}{newline}{stage_line}",
            body,
            count=1,
        )
    return text[:start] + body + text[end:]


def _load(path: Path) -> tuple[str, dict[int, dict]]:
    text = path.read_bytes().decode("utf-8")
    tasks = lint_task_deps.parse_tasks(text)
    if not tasks:
        raise ValueError("未解析到任何任务")
    return text, tasks


def _atomic_write(path: Path, text: str) -> None:
    original_mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}."
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, original_mode)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _write_decisions(
    path: Path, text: str, decisions: list[TaskDecision]
) -> None:
    for decision in decisions:
        text = update_task_state(text, decision)
    _atomic_write(path, text)


def main(argv: list[str]) -> int:
    """Run the workflow control CLI."""
    parser = argparse.ArgumentParser(description="确定性工作流控制流")
    parser.add_argument("tasks_md", type=Path, help="tasks.md 路径")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("waves", help="输出稳定拓扑波次")
    subparsers.add_parser("dispatchable", help="输出当前可调度任务")
    event_parser = subparsers.add_parser("event", help="应用任务控制流事件")
    event_parser.add_argument("task_id", type=int)
    event_parser.add_argument(
        "event",
        choices=(
            "start",
            "failure",
            "quality_passed",
            "merge_success",
            "merge_failure",
            "unblock",
        ),
    )
    event_parser.add_argument("--max-attempts", type=int, default=2)
    event_parser.add_argument("--reason", default="")
    event_parser.add_argument("--write", action="store_true")
    block_parser = subparsers.add_parser("block", help="传播下游阻塞")
    block_parser.add_argument("--write", action="store_true")
    recovery_parser = subparsers.add_parser("recover", help="输出中断恢复计划")
    recovery_parser.add_argument("--merged", nargs="*", type=int, default=[])

    args = parser.parse_args(argv)
    try:
        text, tasks = _load(args.tasks_md)
        if args.command == "waves":
            output = build_waves(tasks)
        elif args.command == "dispatchable":
            output = dispatchable_tasks(tasks)
        elif args.command == "event":
            decision = apply_event(
                tasks, args.task_id, args.event, args.reason, args.max_attempts
            )
            output = asdict(decision)
            if args.write:
                _write_decisions(args.tasks_md, text, [decision])
        elif args.command == "block":
            decisions = propagate_blocked(tasks)
            output = [asdict(decision) for decision in decisions]
            if args.write:
                _write_decisions(args.tasks_md, text, decisions)
        else:
            output = [
                asdict(action)
                for action in plan_recovery(tasks, set(args.merged))
            ]
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
