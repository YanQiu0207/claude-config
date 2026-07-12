#!/usr/bin/env python3
"""研发后验证门禁（框架参考实现）。

读取 verify.config.json，执行其中定义的检查，产出结构化报告。
支持改动前后的基线对比：只把「相对基线新增」的违规判为失败，
从而把「是不是这次引入的」从口头辩解变成两份报告的差集。
同时内置 spec drift 检查：改了代码但规格 / 任务 / ADR 没更新时，
必须提供「无需更新原因」。

用法：
    # 改动前：采集基线
    python verify.py --save-baseline .verify/baseline.json

    # 改动后：验证并与基线对比
    python verify.py --baseline .verify/baseline.json

    # 不带基线：所有检查按绝对标准判定
    python verify.py

退出码：
    0 = 全部通过 / 采集基线成功
    1 = 存在（新增）违规或 spec drift
    2 = 配置或运行错误
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    """单个检查的结果。"""

    name: str
    type: str
    status: str  # "pass"（通过）| "fail"（违规）| "error"（命令/配置执行错误）
    detail: str = ""
    value: Any = None  # 本次测得的值：count 为数字，forbid_pattern 为命中行列表
    new_items: list[str] = field(default_factory=list)  # 相对基线的新增违规行


_DEFAULT_TIMEOUT = 60  # 秒；防止卡死命令永久阻塞验证流程
_CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".py",
    ".rs",
    ".sh",
    ".bat",
    ".cmd",
    ".ps1",
    ".psm1",
    ".psd1",
    ".ts",
    ".tsx",
}
_CODE_FILE_NAMES = {"dockerfile", "makefile"}
_SPEC_FILE_NAMES = {"spec.md", "ui-spec.md", "tasks.md"}
_DOC_SUFFIXES = {".md", ".mdx"}


class CommandTimeout(Exception):
    """命令执行超时。用独立异常而非复用 returncode，避免与 expect_code=1 混淆。"""

    def __init__(self, command: str, timeout: int) -> None:
        super().__init__(f"命令超时（>{timeout}s）：{command[:80]}")


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """强制终止进程及其所有子进程。"""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, timeout=5,
            )
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                proc.kill()
    except Exception:
        proc.kill()


def run_command(command: str, timeout: int = _DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    """执行 shell 命令，返回 (returncode, stdout, stderr)。超时时终止进程树并抛 CommandTimeout。"""
    kwargs: dict[str, Any] = {
        "shell": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "encoding": "utf-8",   # 固定 UTF-8，避免 Windows GBK 等本机编码导致解码崩溃
        "errors": "replace",   # 不可解码字节替换为 U+FFFD，门禁继续产出结构化报告
    }
    if sys.platform != "win32":
        kwargs["start_new_session"] = True  # POSIX：新进程组，方便 killpg
    proc = subprocess.Popen(command, **kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        proc.wait()
        raise CommandTimeout(command, timeout)


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _git_lines(args: list[str]) -> tuple[int, list[str], str]:
    """Run git and return non-empty stdout lines."""
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, _nonempty_lines(proc.stdout), proc.stderr.strip()


def _changed_files(diff_base: str) -> tuple[list[str], list[str], str | None]:
    """Return tracked and untracked changed files relative to diff_base."""
    code, tracked, err = _git_lines(["diff", "--name-only", diff_base, "--"])
    if code != 0:
        return [], [], err or f"git diff failed with exit={code}"
    code, untracked, err = _git_lines(
        ["ls-files", "--others", "--exclude-standard"]
    )
    if code != 0:
        return [], [], err or f"git ls-files failed with exit={code}"
    return sorted(set(tracked)), sorted(set(untracked)), None


def _is_code_file(path_text: str) -> bool:
    path = Path(path_text)
    suffix = path.suffix.lower()
    if suffix in _CODE_SUFFIXES:
        return True
    if path.name.lower() in _CODE_FILE_NAMES:
        return True
    return (
        "scripts" in {part.lower() for part in path.parts}
        and suffix not in _DOC_SUFFIXES
    )


def _is_spec_file(path_text: str) -> bool:
    path = Path(path_text)
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    if name in _SPEC_FILE_NAMES:
        return True
    if path.suffix.lower() in _DOC_SUFFIXES and parts.intersection({"adr", "adrs"}):
        return True
    return False


def evaluate_spec_drift(diff_base: str, reason: str) -> CheckResult:
    """Require an explicit reason when code changed but specs/tasks/ADR did not."""
    tracked, untracked, error = _changed_files(diff_base)
    if error:
        return CheckResult(
            "Z-spec-drift",
            "spec_drift",
            "error",
            f"无法读取 git diff：{error}",
        )

    changed = sorted(set(tracked + untracked))
    code_files = [path for path in changed if _is_code_file(path)]
    spec_files = [path for path in tracked if _is_spec_file(path)]
    untracked_spec_files = [path for path in untracked if _is_spec_file(path)]
    related_spec_files = _related_spec_files(
        code_files, spec_files + untracked_spec_files
    )
    value = {
        "diff_base": diff_base,
        "code_files": code_files,
        "spec_files": spec_files,
        "untracked_spec_files": untracked_spec_files,
        "related_spec_files": related_spec_files,
        "reason": reason,
    }
    if not code_files:
        return CheckResult(
            "Z-spec-drift",
            "spec_drift",
            "pass",
            "无代码文件变更",
            value=value,
        )
    if related_spec_files:
        return CheckResult(
            "Z-spec-drift",
            "spec_drift",
            "pass",
            f"代码变更 {len(code_files)} 个，相关规格类文件已更新 {len(related_spec_files)} 个",
            value=value,
        )
    if reason.strip():
        return CheckResult(
            "Z-spec-drift",
            "spec_drift",
            "pass",
            "代码已变更但规格类文件未变更；已提供无需更新原因",
            value=value,
        )
    return CheckResult(
        "Z-spec-drift",
        "spec_drift",
        "fail",
        "改了代码，但未能证明相关 spec.md / ui-spec.md / tasks.md / ADR 已更新；"
        "请补更新，或通过 --spec-drift-reason 写明无需更新原因",
        value=value,
    )


def _related_spec_files(code_files: list[str], spec_files: list[str]) -> list[str]:
    """Return spec files that can be mechanically tied to changed code files."""
    related: set[str] = set()
    for spec_file in spec_files:
        path = Path(spec_file)
        if path.name.lower() == "tasks.md":
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for code_file in code_files:
                if code_file in body or Path(code_file).as_posix() in body:
                    related.add(spec_file)
                    break
        if path.name.lower() in {"spec.md", "ui-spec.md"}:
            feature_dir = path.parent
            if any(
                _is_relative_to(Path(code_file), feature_dir)
                for code_file in code_files
            ):
                related.add(spec_file)
    return sorted(related)


def _is_relative_to(path: Path, parent: Path) -> bool:
    """Python 3.8 compatible Path.is_relative_to."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


_VALID_DIRECTIONS = {"not_decrease", "not_increase"}


def _check_fingerprint(check: dict) -> dict:
    """提取决定 check 行为的字段，用于检测配置在基线采集后是否被改弱/改变。"""
    ctype = check.get("type", "")
    fp: dict[str, Any] = {"type": ctype, "command": check.get("command", "")}
    if ctype == "count":
        fp["metric"] = check.get("metric", "line_count")
        fp["direction"] = check.get("direction", "not_decrease")
        fp["threshold"] = check.get("threshold")  # 阈值变更会改变判定语义，纳入指纹
    elif ctype == "exit_code":
        fp["expect_code"] = check.get("expect_code", 0)
    return fp


def _config_snapshot(config: dict) -> list[dict]:
    """所有 check 的规范化快照（按 name 排序），用于检测任何 check 被新增/修改/删除。

    覆盖 baseline_aware=false 的 exit_code/count 等关键门槛——这些检查没有
    per-check 指纹，仅靠此快照防止 build/test 检查被静默弱化。
    """
    snap = []
    for check in config.get("checks", []):
        entry = _check_fingerprint(check)
        entry["name"] = check.get("name", "")
        entry["baseline_aware"] = bool(check.get("baseline_aware"))
        snap.append(entry)
    return sorted(snap, key=lambda x: x["name"])


def _extract_executable(command: str) -> str:
    """提取 shell 命令的第一个 token（通常为可执行文件名或路径）。解析失败时回退到按空格分割。"""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.strip().split()
    return tokens[0] if tokens else ""


def _tool_reachable(token: str) -> bool:
    """判断命令 token 是否可访问：含路径分隔符用 exists，纯名称用 shutil.which。"""
    if not token:
        return True
    if os.sep in token or "/" in token:
        return os.path.exists(token)
    return shutil.which(token) is not None


def _measure_count(check: dict, stdout: str) -> int:
    """按 metric 把命令输出折算成一个整数。stdout_int 解析失败时抛 ValueError（不降级为行数）。"""
    metric = check.get("metric", "line_count")
    if metric == "stdout_int":
        stripped = stdout.strip()
        try:
            return int(stripped)
        except ValueError:
            raise ValueError(
                f"stdout_int 解析失败：输出「{stripped[:60]}」不是整数；"
                "如需行数语义请将 metric 改为 line_count"
            )
    return len(_nonempty_lines(stdout))


def evaluate_check(check: dict, baseline: dict | None) -> CheckResult:
    """执行并判定一个检查。baseline 为该检查的基线条目（{type, value}）或 None。"""
    name = check.get("name", "<unnamed>")
    ctype = check.get("type")
    command = check.get("command", "")
    if not ctype or not command:
        return CheckResult(name, ctype or "?", "error", "check 缺少 type 或 command")

    timeout = int(check.get("timeout_seconds") or _DEFAULT_TIMEOUT)
    try:
        returncode, out, err = run_command(command, timeout=timeout)
    except CommandTimeout as exc:
        # 超时独立报 error，不复用任何 returncode，避免与 expect_code 语义冲突
        return CheckResult(name, ctype, "error", str(exc))

    # count: 命令必须以退出码 0 成功，否则判 error——count 命令（输出整数/行数）不存在
    # 「非 0=无匹配」的语义，任何非 0 退出都意味着计数本身失败。
    if ctype == "count" and returncode != 0:
        tail = " | ".join((err or out).strip().splitlines()[-3:]) or f"exit={returncode}"
        return CheckResult(name, ctype, "error", f"命令执行失败 exit={returncode}：{tail}")

    # forbid_pattern 的合法退出码契约：
    #   exit=0 → 扫描成功（stdout 含命中或为空）
    #   exit=1 且无 stderr → grep 无匹配约定，视为「无命中」
    #   exit=1 且有 stderr → 工具报错
    #   exit>=2 → 任何情况均视为执行错误（崩溃、路径错误、工具不存在等）
    # 不能用「有无 stderr」作为唯一判据，exit>=2 无 stderr 也可能是扫描器崩溃。
    if ctype == "forbid_pattern" and returncode not in (0, 1):
        tail = " | ".join((err or out).strip().splitlines()[-3:]) or f"exit={returncode}"
        return CheckResult(name, ctype, "error", f"命令执行失败 exit={returncode}：{tail}")
    if ctype == "forbid_pattern" and returncode == 1 and err.strip():
        tail = " | ".join(err.strip().splitlines()[-3:])
        return CheckResult(name, ctype, "error", f"命令执行失败 exit={returncode}：{tail}")

    if ctype == "exit_code":
        expect = check.get("expect_code", 0)
        # 工具不存在/无执行权限属于门禁自身故障（→ error），而非代码问题（→ fail）。
        # 不先区分两者，expect_code 为某特殊值时工具缺失可能虚假 PASS。
        # POSIX shell: 126=无执行权限，127=命令未找到；Windows cmd: 9009。
        # 跨平台兜底：匹配 stderr 中常见「命令未找到」特征字符串。
        _NOT_FOUND_PHRASES = (
            "command not found",
            "not recognized as an internal or external",
            "not recognized as the name of a cmdlet",
        )
        _stderr_lc = (err or "").lower()
        _shell_not_found = returncode in (126, 127) and not sys.platform.startswith("win")
        _win_not_found = returncode == 9009
        _stderr_not_found = any(p in _stderr_lc for p in _NOT_FOUND_PHRASES)
        if _shell_not_found or _win_not_found or _stderr_not_found:
            tail = " | ".join((err or out).strip().splitlines()[-3:]) or f"exit={returncode}"
            return CheckResult(name, ctype, "error",
                               f"命令不可执行（工具缺失或无执行权限）exit={returncode}：{tail}")
        if returncode == expect:
            # 补充 shutil.which 预检：覆盖 Windows 下缺失命令返回 1（而非 9009）且
            # expect_code=1 导致虚假 PASS 的场景（stderr 被命令自身重定向时尤其危险）。
            first_token = _extract_executable(command)
            if first_token and not _tool_reachable(first_token):
                return CheckResult(
                    name, ctype, "error",
                    f"exit={returncode} 与 expect_code 相同，但 '{first_token}' 未在 PATH 中找到——"
                    "疑似工具缺失导致 exit 与 expect_code 碰巧相同；如确认为 shell 内置命令请忽略此 error",
                )
            return CheckResult(name, ctype, "pass", f"exit={returncode}")
        tail = (err or out).strip().splitlines()[-5:]
        return CheckResult(
            name, ctype, "fail",
            f"exit={returncode} 期望 {expect}；末尾输出：" + " | ".join(tail),
        )

    if ctype == "forbid_pattern":
        items = _nonempty_lines(out)
        if baseline is not None:
            # 校验 value 类型：基线损坏或格式迁移时应 fail-closed，而非被 Counter 静默接受
            # 并把当前命中"计入基线"从而放过新增违规。与 count 的 int 校验保持对称。
            if not isinstance(baseline.get("value"), list):
                return CheckResult(name, ctype, "error",
                                   f"基线 value 类型错误（期望 list，实际 {type(baseline.get('value')).__name__}），需重新运行 --save-baseline 采集基线")
            # 按出现次数比对，而非集合：grep -o 类命令对每处命中只输出相同文本，
            # 用 set 会把「新增的同名违规」误判为已在基线内而放过。
            base_counter = Counter(baseline.get("value") or [])
            new: list[str] = []
            for item, count in Counter(items).items():
                extra = count - base_counter.get(item, 0)
                if extra > 0:
                    new.extend([item] * extra)
            if new:
                return CheckResult(
                    name, ctype, "fail", f"新增 {len(new)} 处违规",
                    value=items, new_items=new,
                )
            return CheckResult(
                name, ctype, "pass", f"命中 {len(items)} 处，均在基线内", value=items,
            )
        if items:
            return CheckResult(
                name, ctype, "fail", f"命中 {len(items)} 处违规",
                value=items, new_items=items,
            )
        return CheckResult(name, ctype, "pass", "无命中", value=items)

    if ctype == "count":
        direction = check.get("direction", "not_decrease")
        if direction not in _VALID_DIRECTIONS:
            return CheckResult(name, ctype, "error",
                               f"count.direction 值「{direction}」无效，必须为 {sorted(_VALID_DIRECTIONS)}")
        try:
            current = _measure_count(check, out)
        except ValueError as exc:
            return CheckResult(name, ctype, "error", str(exc))
        if baseline is not None:
            if not isinstance(baseline.get("value"), int):
                return CheckResult(name, ctype, "error",
                                   f"基线 value 类型错误（期望 int，实际 {type(baseline.get('value')).__name__}），需重新采集基线")
            base_val = baseline["value"]
            if direction == "not_decrease" and current < base_val:
                return CheckResult(name, ctype, "fail", f"{current} < 基线 {base_val}", value=current)
            if direction == "not_increase" and current > base_val:
                return CheckResult(name, ctype, "fail", f"{current} > 基线 {base_val}", value=current)
            # 有基线时 threshold 依然作为绝对保障下/上限——否则基线本身偏低时
            # threshold 形同虚设，配置作者声明的最低门槛永远不生效。
            threshold = check.get("threshold")
            if isinstance(threshold, int):
                if direction == "not_decrease" and current < threshold:
                    return CheckResult(name, ctype, "fail",
                                       f"{current} < 绝对下限 {threshold}（基线 {base_val}）", value=current)
                if direction == "not_increase" and current > threshold:
                    return CheckResult(name, ctype, "fail",
                                       f"{current} > 绝对上限 {threshold}（基线 {base_val}）", value=current)
            return CheckResult(name, ctype, "pass", f"{current}（基线 {base_val}）", value=current)
        threshold = check.get("threshold")
        if not isinstance(threshold, int):
            # 无基线、无合法 threshold：无法做任何判断，应在 schema 校验阶段阻止；
            # 若运行时仍到此（如直接调用 evaluate_check），报 error 而不是静默 pass。
            return CheckResult(name, ctype, "error",
                               "count 检查无可用基线且无整数 threshold，无法判定；"
                               "请添加 threshold 或使用 baseline_aware + --baseline 运行")
        # not_decrease → threshold 为下限，current 不得低于它
        # not_increase → threshold 为上限，current 不得高于它
        if direction == "not_decrease" and current < threshold:
            return CheckResult(name, ctype, "fail", f"{current} < 下限阈值 {threshold}", value=current)
        if direction == "not_increase" and current > threshold:
            return CheckResult(name, ctype, "fail", f"{current} > 上限阈值 {threshold}", value=current)
        return CheckResult(name, ctype, "pass", f"{current}", value=current)

    return CheckResult(name, ctype, "error", f"未知 check 类型：{ctype}")


def _validate_config(config: dict, path: Path) -> None:
    """校验配置 schema；不合规则打印错误并 sys.exit(2)。"""
    if not isinstance(config, dict):
        print(f"[verify] 配置格式错误：顶层必须为 JSON 对象（{path}）。", file=sys.stderr)
        sys.exit(2)
    checks = config.get("checks")
    if checks is None:
        print(f"[verify] 配置缺少 checks 字段（{path}）。", file=sys.stderr)
        sys.exit(2)
    if not isinstance(checks, list):
        print(f"[verify] checks 必须是列表（{path}）。", file=sys.stderr)
        sys.exit(2)
    if len(checks) == 0:
        print(f"[verify] checks 为空列表，没有任何检查项（{path}）。", file=sys.stderr)
        sys.exit(2)
    names: list[str] = []
    for i, item in enumerate(checks):
        if not isinstance(item, dict):
            print(f"[verify] checks[{i}] 不是对象（{path}）。", file=sys.stderr)
            sys.exit(2)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            print(f"[verify] checks[{i}].name 缺失或不是非空字符串（{path}）。", file=sys.stderr)
            sys.exit(2)
        if name in names:
            print(f"[verify] check 名称重复：「{name}」（{path}）。", file=sys.stderr)
            sys.exit(2)
        names.append(name)
        _validate_check_item(i, name, item, path)


_ALLOWED_TYPES = {"exit_code", "forbid_pattern", "count"}
_ALLOWED_METRICS = {"line_count", "stdout_int"}


def _validate_check_item(i: int, name: str, item: dict, path: Path) -> None:
    """校验单个 check 条目的字段合法性；不合规则打印错误并 sys.exit(2)。"""

    def fail(msg: str) -> None:
        print(f"[verify] checks[{i}]（name={name!r}）{msg}（{path}）。", file=sys.stderr)
        sys.exit(2)

    ctype = item.get("type")
    if ctype not in _ALLOWED_TYPES:
        fail(f"type={ctype!r} 无效，必须为 {sorted(_ALLOWED_TYPES)}")

    command = item.get("command")
    if not isinstance(command, str) or not command.strip():
        fail("command 缺失或不是非空字符串")

    ts = item.get("timeout_seconds")
    if ts is not None and (not isinstance(ts, int) or ts <= 0):
        fail(f"timeout_seconds={ts!r} 无效，必须为正整数")

    if ctype == "exit_code":
        ec = item.get("expect_code", 0)
        if not isinstance(ec, int):
            fail(f"expect_code={ec!r} 无效，必须为整数")

    if ctype == "count":
        metric = item.get("metric", "line_count")
        if metric not in _ALLOWED_METRICS:
            fail(f"metric={metric!r} 无效，必须为 {sorted(_ALLOWED_METRICS)}")
        direction = item.get("direction", "not_decrease")
        if direction not in _VALID_DIRECTIONS:
            fail(f"direction={direction!r} 无效，必须为 {sorted(_VALID_DIRECTIONS)}")
        threshold = item.get("threshold")
        if not isinstance(threshold, int):
            fail("type=count 必须提供整数 threshold（无基线时作为绝对判定依据；有基线时作为最低保障值）")


def load_config(path: Path, require: bool = False) -> dict:
    """读配置。

    不存在时：
    - require=False（无基线模式）→ 返回空 checks，仅跑内置门禁。
    - require=True（--baseline / --save-baseline 模式）→ exit 2，已有基线的验证场景
      配置缺失属于门禁本身故障，不能视为"跳过"。
    """
    if not path.exists():
        if require:
            print(f"[verify] 配置文件不存在：{path}；"
                  "--baseline/--save-baseline 模式下配置必须存在（不能静默跳过）。", file=sys.stderr)
            sys.exit(2)
        print(f"[verify] 未找到配置 {path}，仅运行内置门禁。")
        return {"checks": []}
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[verify] 配置解析失败：{exc}", file=sys.stderr)
        sys.exit(2)
    _validate_config(config, path)
    return config


def _atomic_write_json(path: Path, data: Any) -> None:
    """原子写入 JSON：先写临时文件再 os.replace，防止中断破坏已有文件。"""
    import tempfile
    content = json.dumps(data, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def cmd_save_baseline(config: dict, out_path: Path) -> int:
    """采集基线：只记录 baseline_aware 检查的当前"值"。

    forbid_pattern 的 fail 表示「记录已存在的违规」，属正常用途，写入基线。
    count 的 fail 表示「已违反绝对 threshold」，不能写入——否则后续无改动也会 FAIL，
    导致门禁自相矛盾；与 error 同等处理，中止采集。
    """
    baseline: dict[str, Any] = {"checks": {}, "config_snapshot": _config_snapshot(config)}
    blocked: list[CheckResult] = []
    for check in config.get("checks", []):
        if not check.get("baseline_aware"):
            continue
        res = evaluate_check(check, baseline=None)
        # count 的 fail = 当前值已低于绝对 threshold，写入此值会让后续基线对比永久失败
        if res.status == "error" or (res.status == "fail" and res.type == "count"):
            blocked.append(res)
            continue
        baseline["checks"][res.name] = {
            "type": res.type,
            "value": res.value,
            "fingerprint": _check_fingerprint(check),
        }
    if blocked:
        print("[verify] 基线采集失败：以下检查无法产出可用基线，已中止。", file=sys.stderr)
        for r in blocked:
            tag = "[ERROR]" if r.status == "error" else "[FAIL] "
            print(f"  {tag} {r.name} [{r.type}] {r.detail}", file=sys.stderr)
        return 2
    try:
        _atomic_write_json(out_path, baseline)
    except OSError as exc:
        print(f"[verify] 基线写入失败：{exc}", file=sys.stderr)
        return 2
    print(f"[verify] 基线已保存到 {out_path}（{len(baseline['checks'])} 项 baseline-aware 检查）")
    return 0


def cmd_verify(
    config: dict,
    baseline_path: Path | None,
    report_path: Path,
    diff_base: str,
    spec_drift_reason: str,
) -> int:
    """跑全部检查，对 baseline_aware 项做基线对比，产出报告。"""
    # 显式传了 --baseline 但文件不存在 → fail-closed，不能静默降级为无基线模式
    if baseline_path is not None and not baseline_path.exists():
        print(f"[verify] 指定了 --baseline 但文件不存在：{baseline_path}，需先运行 --save-baseline 采集基线。", file=sys.stderr)
        return 2

    baseline_data: dict[str, Any] = {}
    if baseline_path and baseline_path.exists():
        try:
            raw = json.loads(baseline_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[verify] 基线解析失败：{exc}", file=sys.stderr)
            return 2
        if not isinstance(raw, dict):
            print(f"[verify] 基线格式错误：顶层必须为 JSON 对象（{baseline_path}）。", file=sys.stderr)
            return 2
        checks_raw = raw.get("checks", {})
        if not isinstance(checks_raw, dict):
            print(f"[verify] 基线格式错误：checks 必须为对象（{baseline_path}）。", file=sys.stderr)
            return 2
        for k, v in checks_raw.items():
            if not isinstance(v, dict):
                print(f"[verify] 基线格式错误：checks.{k!r} 必须为对象（{baseline_path}）。", file=sys.stderr)
                return 2
        baseline_data = checks_raw

        # 全配置快照校验：覆盖所有 check（含 baseline_aware=false 的 build/test 等）。
        # 任何 check 被新增/修改/删除 → fail-closed，防止在同一次变更里静默弱化门禁。
        # 旧基线缺失 config_snapshot → 同样 fail-closed，要求重建基线——
        # 不能 fail-open，否则版本升级时旧基线对非 baseline_aware 检查完全失去保护。
        stored_snap = raw.get("config_snapshot")
        if not isinstance(stored_snap, list):
            print(
                "[verify] 基线缺少合法 config_snapshot（旧版基线或结构损坏），"
                "需重新运行 --save-baseline 重建基线。",
                file=sys.stderr,
            )
            return 2
        current_snap = _config_snapshot(config)
        # 按 check 粒度比对快照：删除或修改已有检查 → fail-closed（防门禁被弱化）；
        # 新增检查 → 放行，以绝对模式执行，无需重建基线。
        # 全量相等比对会把「同一 PR 合法新增 check + 跑 --baseline」阻断，
        # 迫使工程师在改后状态重采基线，新增违规可能被记入历史基线而绕过保护。
        stored_by_name = {e["name"]: e for e in stored_snap}
        current_by_name = {e["name"]: e for e in current_snap}
        for sname, stored_entry in stored_by_name.items():
            cur_entry = current_by_name.get(sname)
            if cur_entry is None:
                print(
                    f"[verify] check '{sname}' 在基线中存在但已从配置中移除，"
                    "需重新运行 --save-baseline 更新基线后再验证。",
                    file=sys.stderr,
                )
                return 2
            if cur_entry != stored_entry:
                print(
                    f"[verify] check '{sname}' 配置已变更（命令、阈值或类型与基线不一致），"
                    "需重新运行 --save-baseline 更新基线后再验证。",
                    file=sys.stderr,
                )
                return 2
        # stored_by_name 中未出现的 check → 本次新增，以绝对模式执行，无需 rebaseline。

    results: list[CheckResult] = [
        evaluate_spec_drift(diff_base, spec_drift_reason)
    ]
    for check in config.get("checks", []):
        name = check.get("name", "<unnamed>")
        base_entry = None
        if check.get("baseline_aware"):
            if baseline_path is not None:
                # baseline 显式指定：baseline_aware 检查必须在基线中；
                # 缺失条目不降级为无基线模式（count 无基线会静默 pass，门禁形同虚设）
                if name not in baseline_data:
                    results.append(CheckResult(
                        name, check.get("type", "?"), "error",
                        "baseline_aware 检查在基线文件中无对应条目，需重新运行 --save-baseline 更新基线",
                    ))
                    continue
                base_entry = baseline_data[name]
                # 校验 check 指纹：如果 command/direction 等关键字段在采集基线后被改变，
                # 已存储的基线值不再对应当前检查的语义，继续对比会产生错误结论。
                stored_fp = base_entry.get("fingerprint")
                # fingerprint 缺失（旧基线/损坏）视为配置漂移检测不可信，fail-closed。
                # 不静默接受旧基线：accept 旧 value 但跳过指纹校验会让配置弱化后仍 PASS。
                if not isinstance(stored_fp, dict):
                    results.append(CheckResult(
                        name, check.get("type", "?"), "error",
                        "基线条目缺少合法 fingerprint（旧版或损坏基线），需重新运行 --save-baseline 重建基线",
                    ))
                    continue
                current_fp = _check_fingerprint(check)
                if current_fp != stored_fp:
                    results.append(CheckResult(
                        name, check.get("type", "?"), "error",
                        f"check 配置与采集基线时不一致，需重新运行 --save-baseline 更新基线"
                        f"（存储：{stored_fp}，当前：{current_fp}）",
                    ))
                    continue
            # baseline_path 为 None → 不带基线运行，对存量项目无侵入
        results.append(evaluate_check(check, base_entry))

    # 孤儿基线条目检查：baseline 中存在记录，但当前 config 已关闭 baseline_aware 或删除该 check。
    # 不报 error 则攻击者可把 baseline_aware 改为 false 或删 check，从而绕过基线对比。
    if baseline_path is not None:
        active_aware = {c["name"] for c in config.get("checks", []) if c.get("baseline_aware")}
        for orphan_name in baseline_data:
            if orphan_name not in active_aware:
                results.append(CheckResult(
                    orphan_name, "?", "error",
                    "基线中存在该检查的记录，但当前配置已关闭 baseline_aware 或移除该检查——"
                    "属于配置漂移，需重新运行 --save-baseline 更新基线（或恢复 baseline_aware）",
                ))

    errors = [r for r in results if r.status == "error"]
    violations = [r for r in results if r.status == "fail"]
    # 退出码语义：0 = 全部通过；1 = 有新增违规（可修复）；2 = 门禁本身出错（工具/配置问题）
    # 区分两种非 0 状态，避免把「门禁失效」当「有违规」送进修复循环。
    verdict = "ERROR" if errors else ("FAIL" if violations else "PASS")
    report = {
        "verdict": verdict,
        "total": len(results),
        "errors": len(errors),
        "violations": len(violations),
        "spec_drift": asdict(results[0]) if results else None,
        "results": [asdict(r) for r in results],
    }
    try:
        _atomic_write_json(report_path, report)
    except OSError as exc:
        print(f"[verify] 报告写入失败：{exc}", file=sys.stderr)
        return 2

    _print_summary(results, verdict, report_path)
    if errors:
        return 2
    return 1 if violations else 0


def _print_summary(results: list[CheckResult], verdict: str, report_path: Path) -> None:
    print("\n==== verify 门禁结果 ====")
    for r in results:
        mark = {"pass": "[PASS]", "fail": "[FAIL]", "error": "[ERR ]"}.get(r.status, "[????]")
        print(f"{mark} {r.name} [{r.type}] {r.detail}")
        for item in r.new_items[:10]:
            print(f"        新增违规：{item}")
    print(f"\n总判定：{verdict}（报告：{report_path}）")


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")  # 避免 Windows 控制台中文乱码
    parser = argparse.ArgumentParser(description="研发后验证门禁（配置驱动 + 基线对比）")
    parser.add_argument("--config", default="verify.config.json", help="配置文件路径")
    parser.add_argument("--save-baseline", metavar="PATH", help="采集基线并写入该路径")
    parser.add_argument("--baseline", metavar="PATH", help="对比用的基线路径")
    parser.add_argument("--report", default=".verify/report.json", help="结构化报告输出路径")
    parser.add_argument(
        "--diff-base",
        default="HEAD",
        help="spec drift 检查的 git diff 基准，默认 HEAD",
    )
    parser.add_argument(
        "--spec-drift-reason",
        default="",
        help="代码变更但无需更新 spec / ui-spec / tasks / ADR 时的原因",
    )
    args = parser.parse_args(argv)

    require_config = bool(args.save_baseline or args.baseline)
    config = load_config(Path(args.config), require=require_config)

    if args.save_baseline:
        return cmd_save_baseline(config, Path(args.save_baseline))

    baseline_path = Path(args.baseline) if args.baseline else None
    return cmd_verify(
        config,
        baseline_path,
        Path(args.report),
        args.diff_base,
        args.spec_drift_reason,
    )


if __name__ == "__main__":
    sys.exit(main())
