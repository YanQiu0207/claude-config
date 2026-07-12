"""Deterministic control-flow decisions for workflow tasks."""

from __future__ import annotations

import argparse
import contextlib
import errno
import json
import math
import os
import re
import stat
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import lint_task_deps


_LOCK_POLL_INTERVAL_SECONDS = 0.05


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
    if not value.isdecimal():
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


def _kahn_waves(tasks: dict[int, dict]) -> list[list[int]]:
    """Layer tasks via Kahn topological sort; raise on cyclic dependencies."""
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


def _validate_dependencies(tasks: dict[int, dict]) -> list[list[int]]:
    """Validate dependency fields; reject cycles; return the waves."""
    for task_id, task in tasks.items():
        if not task["has_dep_field"]:
            raise ValueError(f"任务 {task_id} 缺少 depends_on 字段")
        missing = task["deps"] - tasks.keys()
        if missing:
            raise ValueError(f"任务 {task_id} 依赖不存在的任务 {min(missing)}")
    return _kahn_waves(tasks)


def _validate_reason(reason: str) -> None:
    if "\r" in reason or "\n" in reason:
        raise ValueError("原因不能包含换行符")


def build_waves(tasks: dict[int, dict]) -> list[list[int]]:
    """Build stable topological waves from parsed tasks."""
    return _validate_dependencies(tasks)


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


_VALID_TRANSITIONS = {
    ("未开始", "pending", "start"),
    ("进行中", "running", "failure"),
    ("进行中", "running", "quality_passed"),
    ("进行中", "running", "manual"),
    ("进行中", "quality_passed", "merge_success"),
    ("进行中", "quality_passed", "merge_failure"),
    ("需人工", "manual", "manual_resolved"),
    ("阻塞", "blocked", "unblock"),
}


def _require_completed_dependencies(
    tasks: dict[int, dict], task_id: int, state: str, event: str
) -> None:
    """Raise unless every dependency of task_id is already 完成."""
    states = _states(tasks)
    if any(
        states[dependency] != "完成" for dependency in tasks[task_id]["deps"]
    ):
        raise ValueError(
            f"任务 {task_id} 的前置依赖尚未全部完成，无法从 {state} 执行 {event}"
        )


def _handle_start(
    tasks: dict[int, dict],
    task_id: int,
    state: str,
    reason: str,
    attempts: int,
) -> TaskDecision:
    _require_completed_dependencies(tasks, task_id, state, "start")
    return TaskDecision(
        task_id, "进行中", "dispatch", reason, attempts, "running"
    )


def _handle_quality_passed(
    task_id: int, reason: str, attempts: int
) -> TaskDecision:
    return TaskDecision(
        task_id, "进行中", "merge", reason, attempts, "quality_passed"
    )


def _handle_merge_success(
    task_id: int, reason: str, attempts: int
) -> TaskDecision:
    return TaskDecision(
        task_id, "完成", "complete", reason, attempts, "completed"
    )


def _handle_merge_failure(
    task_id: int, reason: str, attempts: int
) -> TaskDecision:
    return TaskDecision(task_id, "需人工", "manual", reason, attempts, "manual")


def _handle_manual(task_id: int, reason: str, attempts: int) -> TaskDecision:
    if not reason:
        raise ValueError(f"任务 {task_id} 的 manual 事件必须提供原因")
    return TaskDecision(task_id, "需人工", "manual", reason, attempts, "manual")


def _handle_manual_resolved(
    task_id: int, reason: str, attempts: int
) -> TaskDecision:
    return TaskDecision(
        task_id, "完成", "complete", reason, attempts, "completed"
    )


def _handle_unblock(
    tasks: dict[int, dict],
    task_id: int,
    state: str,
    reason: str,
    attempts: int,
) -> TaskDecision:
    _require_completed_dependencies(tasks, task_id, state, "unblock")
    return TaskDecision(
        task_id, "未开始", "unblock", reason, attempts, "pending"
    )


def _handle_failure(
    task_id: int, reason: str, attempts: int, max_attempts: int
) -> TaskDecision:
    attempts += 1
    if attempts <= max_attempts:
        return TaskDecision(
            task_id, "进行中", "retry", reason, attempts, "running"
        )
    exhausted = reason or f"修复次数已耗尽（{attempts - 1}/{max_attempts}）"
    return TaskDecision(
        task_id, "需人工", "manual", exhausted, attempts, "manual"
    )


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
    if (state, stage, event) not in _VALID_TRANSITIONS:
        raise ValueError(
            f"任务 {task_id} 不允许从 {state}/{stage} 执行 {event}"
        )
    if event == "start":
        return _handle_start(tasks, task_id, state, reason, attempts)
    if event == "quality_passed":
        return _handle_quality_passed(task_id, reason, attempts)
    if event == "merge_success":
        return _handle_merge_success(task_id, reason, attempts)
    if event == "merge_failure":
        return _handle_merge_failure(task_id, reason, attempts)
    if event == "manual":
        return _handle_manual(task_id, reason, attempts)
    if event == "manual_resolved":
        return _handle_manual_resolved(task_id, reason, attempts)
    if event == "unblock":
        return _handle_unblock(tasks, task_id, state, reason, attempts)
    if event == "failure":
        return _handle_failure(task_id, reason, attempts, max_attempts)
    raise ValueError(f"未知事件: {event}")


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


def _check_merge_state_conflict(
    task_id: int, state: str, merged_task_ids: set[int]
) -> None:
    """Reject external merge facts that contradict persisted state."""
    if state in {"未开始", "阻塞"} and task_id in merged_task_ids:
        raise ValueError(
            f"任务 {task_id} 状态为 {state} 但出现在已合并集合中，"
            "外部合并事实与持久化状态矛盾"
        )


def _recovery_action_for(
    task_id: int,
    state: str,
    merged_task_ids: set[int],
    deps_complete: bool,
) -> RecoveryAction:
    """Decide one task's recovery action by its own state, in priority order."""
    if state == "完成":
        return RecoveryAction(task_id, "skip", "任务已完成")
    if state == "需人工" and task_id in merged_task_ids:
        return RecoveryAction(task_id, "complete", "任务已人工解决并合并")
    if state == "需人工":
        return RecoveryAction(
            task_id, "manual", "等待人工处理，处理并合并后重跑 recover"
        )
    if state == "进行中" and task_id in merged_task_ids:
        return RecoveryAction(task_id, "complete", "任务分支已合并")
    if state == "进行中":
        return RecoveryAction(
            task_id, "inspect", "任务未合并，检查产物和质量门"
        )
    if state == "阻塞" and deps_complete:
        return RecoveryAction(task_id, "unblock", "全部上游已完成")
    if state == "未开始" and deps_complete:
        return RecoveryAction(task_id, "dispatch", "前置依赖已完成")
    return RecoveryAction(task_id, "wait", "前置依赖未完成")


def plan_recovery(
    tasks: dict[int, dict], merged_task_ids: set[int]
) -> list[RecoveryAction]:
    """Plan recovery using task state and externally supplied merge facts."""
    _validate_dependencies(tasks)
    unknown = merged_task_ids - tasks.keys()
    if unknown:
        raise ValueError(f"已合并集合包含未知任务 {min(unknown)}")
    states = _states(tasks)
    for task_id in sorted(tasks):
        _check_merge_state_conflict(task_id, states[task_id], merged_task_ids)
    effective = {**states, **{task_id: "完成" for task_id in merged_task_ids}}
    actions = []
    for task_id in sorted(tasks):
        deps_complete = all(
            effective[dependency] == "完成"
            for dependency in tasks[task_id]["deps"]
        )
        actions.append(
            _recovery_action_for(
                task_id, states[task_id], merged_task_ids, deps_complete
            )
        )
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


def _field_pattern(name: str) -> re.Pattern[str]:
    """Build a MULTILINE pattern that captures a field line's indent."""
    return re.compile(
        r"^([ \t]*)-[ \t]*" + name + r"[ \t]*[:：][^\r\n]*", re.MULTILINE
    )


def _replace_or_insert_after(
    body: str,
    pattern: re.Pattern[str],
    anchor: re.Pattern[str],
    line_text: str,
    newline: str,
) -> str:
    """Replace a field line in place, or insert it right after an anchor line.

    Both branches pass a callable to `re.sub` so `line_text` (which may embed
    caller-supplied text such as a failure reason) is never parsed as a
    backreference template.
    """
    if pattern.search(body):
        return pattern.sub(
            lambda match: f"{match.group(1)}{line_text}", body, count=1
        )
    return anchor.sub(
        lambda match: (f"{match.group(0)}{newline}{match.group(1)}{line_text}"),
        body,
        count=1,
    )


def update_task_state(text: str, decision: TaskDecision) -> str:
    """Precisely persist one validated decision without reserializing Markdown."""
    _validate_reason(decision.reason)
    start, end = _task_bounds(text, decision.task_id)
    body = text[start:end]
    newline = "\r\n" if "\r\n" in text else "\n"

    status_pattern = _field_pattern("状态")
    if not status_pattern.search(body):
        raise ValueError(f"任务 {decision.task_id} 缺少状态字段")
    status_line = f"- 状态：{decision.state}"
    if decision.reason:
        status_line += f"（{decision.reason}）"
    body = status_pattern.sub(
        lambda match: f"{match.group(1)}{status_line}", body, count=1
    )

    attempts_pattern = _field_pattern("attempts")
    attempts_line = f"- attempts：{decision.attempts}"
    body = _replace_or_insert_after(
        body, attempts_pattern, status_pattern, attempts_line, newline
    )

    stage_pattern = _field_pattern("control_stage")
    stage_line = f"- control_stage：{decision.control_stage}"
    body = _replace_or_insert_after(
        body, stage_pattern, attempts_pattern, stage_line, newline
    )

    return text[:start] + body + text[end:]


def _load(path: Path) -> tuple[str, dict[int, dict]]:
    text = path.read_bytes().decode("utf-8-sig")
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


def _try_lock(stream) -> bool:
    """Try to acquire an exclusive OS lock without blocking."""
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                return False
            raise
        return True

    import fcntl

    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _unlock(stream) -> None:
    """Release an exclusive OS lock."""
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _task_write_lock(path: Path, timeout: float):
    """Acquire the task file's cross-process write lock within timeout."""
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("锁超时必须是大于等于 0 的有限数")
    lock_path = path.parent / f".{path.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while not _try_lock(stream):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"等待写锁 {lock_path} 超时（{timeout:g} 秒）"
                )
            time.sleep(min(_LOCK_POLL_INTERVAL_SECONDS, remaining))
        try:
            yield
        finally:
            _unlock(stream)


def _write_decisions(
    path: Path, text: str, decisions: list[TaskDecision]
) -> None:
    for decision in decisions:
        text = update_task_state(text, decision)
    _atomic_write(path, text)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for all workflow_control subcommands."""
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
            "manual",
            "manual_resolved",
            "unblock",
        ),
    )
    event_parser.add_argument("--max-attempts", type=int, default=2)
    event_parser.add_argument("--reason", default="")
    event_parser.add_argument("--write", action="store_true")
    event_parser.add_argument("--lock-timeout", type=float, default=10.0)
    block_parser = subparsers.add_parser("block", help="传播下游阻塞")
    block_parser.add_argument("--write", action="store_true")
    block_parser.add_argument("--lock-timeout", type=float, default=10.0)
    recovery_parser = subparsers.add_parser("recover", help="输出中断恢复计划")
    recovery_parser.add_argument("--merged", nargs="*", type=int, default=[])
    return parser


def main(argv: list[str]) -> int:
    """Run the workflow control CLI."""
    args = _build_arg_parser().parse_args(argv)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(
                encoding="utf-8"
            )  # 避免 Windows 控制台中文乱码
        is_write = args.command in {"event", "block"} and args.write
        if is_write:
            with _task_write_lock(args.tasks_md, args.lock_timeout):
                text, tasks = _load(args.tasks_md)
                if args.command == "event":
                    decision = apply_event(
                        tasks,
                        args.task_id,
                        args.event,
                        args.reason,
                        args.max_attempts,
                    )
                    output = asdict(decision)
                    _write_decisions(args.tasks_md, text, [decision])
                else:
                    decisions = propagate_blocked(tasks)
                    output = [asdict(decision) for decision in decisions]
                    _write_decisions(args.tasks_md, text, decisions)
        else:
            text, tasks = _load(args.tasks_md)
            if args.command == "waves":
                output = build_waves(tasks)
            elif args.command == "dispatchable":
                output = dispatchable_tasks(tasks)
            elif args.command == "event":
                decision = apply_event(
                    tasks,
                    args.task_id,
                    args.event,
                    args.reason,
                    args.max_attempts,
                )
                output = asdict(decision)
            elif args.command == "block":
                decisions = propagate_blocked(tasks)
                output = [asdict(decision) for decision in decisions]
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
