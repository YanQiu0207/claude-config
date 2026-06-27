# verify.config.json 配置指南

面向人：怎么写配置、怎么接入自己的校验脚本。`<skill-dir>` 指本 skill 安装目录。

## 快速开始

```bash
# 1. 复制示例到项目根
cp <skill-dir>/reference/verify.config.example.json verify.config.json
# 2. 按技术栈改每个 check 的 command（见下方片段）
# 3. 把 .verify/ 加进 .gitignore（基线和报告是本地临时产物）
```

无 `verify.config.json` 时，仍会运行内置 spec drift 检查；项目自定义 build/test/lint 检查跳过。

## 配置结构

```jsonc
{
  "checks": [
    { "name": "B-build", "type": "exit_code", "command": "go build ./...", "expect_code": 0 },
    { "name": "B-tests", "type": "count", "command": "grep -rHo 'def test_' tests/ || true",
      "metric": "line_count", "direction": "not_decrease", "baseline_aware": true, "threshold": 0 }
  ]
}
```

### 字段速查

| 字段 | 适用 type | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | 全部 | 是 | check 名，报告里用 |
| `type` | 全部 | 是 | `exit_code` / `forbid_pattern` / `count` |
| `command` | 全部 | 是 | shell 命令字符串（`shell=True` 执行） |
| `expect_code` | exit_code | 否 | 期望退出码，默认 `0` |
| `baseline_aware` | forbid_pattern / count | 否 | `true` 则参与基线对比，只追新增；默认 `false` |
| `metric` | count | 否 | `line_count`（输出行数）或 `stdout_int`（输出本身是数字），默认 `line_count` |
| `direction` | count | 否 | `not_decrease`（不得减少）/ `not_increase`（不得增加），默认 `not_decrease` |
| `threshold` | count | **是** | 整数。无基线时作绝对判定；有基线时作绝对下 / 上限保障 |
| `timeout_seconds` | 全部 | 否 | 正整数，默认 60 |

## 三类检查

### exit_code —— 交付门槛 / 自定义校验

退出码 == `expect_code`（默认 0）即通过。编译、测试、以及**你自己的校验脚本**都用这类。

```jsonc
{ "name": "B-build", "type": "exit_code", "command": "go build ./...", "expect_code": 0 }
{ "name": "B-tests", "type": "exit_code", "command": "pytest -q", "expect_code": 0 }
```

> 工具缺失保护：若命令首个 token 不在 PATH 且退出码恰好等于 `expect_code`，会报 error（疑似工具没装导致假 PASS），而非 PASS。

### forbid_pattern —— 静态规范

命令命中的**每一行算一处违规**。配 `baseline_aware: true` 时只判超出基线的新增违规，历史遗留不阻塞。

```jsonc
{ "name": "A-no-messagebox", "type": "forbid_pattern",
  "command": "grep -rHo --include=*.cs \"MessageBox\\.Show\" src/", "baseline_aware": true }
```

> ⚠️ 命令必须用 **`-H`（保留文件路径）、不带行号**：输出「文件路径:匹配内容」，这样跨文件移动同名违规可追踪，行号漂移也不会把历史违规误判为新增。

### count —— 工程一致性

把命令输出折算成一个数，按 `direction` 与基线 / 阈值比。典型用途：测试数不减少、文件不超长。

```jsonc
{ "name": "B-test-count", "type": "count",
  "command": "grep -rHo \"def test_\" tests/ || true",
  "metric": "line_count", "direction": "not_decrease", "baseline_aware": true, "threshold": 0 }
```

> `count` 的命令在**零匹配**时也必须 exit 0（grep 无匹配返回 1），故结尾加 `|| true`，stdout 为空则计为 0。`threshold` 必填：无基线时它是绝对下 / 上限。

## 接入自己的脚本

写自定义校验逻辑时，**写一个脚本，按你想要的判定方式选 type**：

| 你的脚本怎么表达结果 | 选哪类 | 例子 |
| --- | --- | --- |
| 返回退出码（0 过 / 非 0 不过） | `exit_code` | `python scripts/check_csproj.py` 校验 .cs 都进了 .csproj |
| 输出违规行（每行一处，可基线对比） | `forbid_pattern` | 脚本打印每个越界 import 的「文件路径:内容」 |
| 输出一个数字（可基线对比方向） | `count` + `metric: stdout_int` | 脚本算出循环复杂度总分，要求不增加 |

最常用是 `exit_code`：

```jsonc
{ "name": "C-arch-boundary", "type": "exit_code",
  "command": "python scripts/check_arch.py", "expect_code": 0 }
```

脚本约定：
- **退出码**就是判定（exit_code 类只看退出码，不看 stdout）。
- 想参与基线对比 → 用 `forbid_pattern`（输出违规行）或 `count` + `stdout_int`（输出数字），并设 `baseline_aware: true`。
- 脚本用项目自己的解释器 / 依赖，门禁只负责 `shell=True` 跑命令字符串。

## 基线对比怎么用

只有 `baseline_aware: true` 的 check 参与。流程：

```bash
# 改动前采基线（只记录 baseline_aware check 的「值」）
python <skill-dir>/scripts/verify.py --save-baseline .verify/baseline.json
# 改动后验证并对比
python <skill-dir>/scripts/verify.py --baseline .verify/baseline.json
```

- `forbid_pattern`：按出现次数比，只对**超出基线的新增命中**判 fail。
- `count`：`not_decrease` 要求 current ≥ 基线，`not_increase` 要求 current ≤ 基线。
- 下放并行执行在 git worktree 内，基线须用**主仓库根绝对路径**（worktree 看不到未提交的 `.verify/`）。

退出码：`0` 全过；`1` 有新增违规或 spec drift（进修复循环）；`2` 门禁自身出错——工具缺失、正则非法、基线损坏（先排查配置，别改代码）。

## 内置 spec drift 检查

不用写进 `verify.config.json`，`verify.py` 默认执行。

规则：

- 本次 git diff 有代码文件变更。
- 但无法机械证明相关 `spec.md`、`ui-spec.md`、`tasks.md` 或 ADR 已变更。
- 且未传 `--spec-drift-reason`。

相关性只做轻量判定：`tasks.md` 中出现代码路径，或代码文件位于同一规格目录下。判不出相关时，宁可要求写明原因。

标准 / 下放流程要在动代码前记录 `base_sha`，验证时传入：

```bash
# 有 verify.config.json
python <skill-dir>/scripts/verify.py \
  --baseline <repo-root>/.verify/baseline.json \
  --diff-base <base_sha>

# 无 verify.config.json
python <skill-dir>/scripts/verify.py --diff-base <base_sha>
```

命中时返回 `1`，交付前必须二选一：

```bash
# 方案 1：补文档 / 任务 / ADR 后重跑（有 config）
python <skill-dir>/scripts/verify.py \
  --baseline <repo-root>/.verify/baseline.json \
  --diff-base <base_sha>

# 方案 1：补文档 / 任务 / ADR 后重跑（无 config）
python <skill-dir>/scripts/verify.py --diff-base <base_sha>

# 方案 2：确实无需更新时写明原因（有 config）
python <skill-dir>/scripts/verify.py \
  --baseline <repo-root>/.verify/baseline.json \
  --diff-base <base_sha> \
  --spec-drift-reason "仅修复脚本输出编码，不改变需求、任务拆解或架构决策"

# 方案 2：确实无需更新时写明原因（无 config）
python <skill-dir>/scripts/verify.py \
  --diff-base <base_sha> \
  --spec-drift-reason "仅修复脚本输出编码，不改变需求、任务拆解或架构决策"
```

报告会写入 `.verify/report.json` 的 `spec_drift` 字段，最终交付证据必须引用其结论。

## 常见技术栈片段

```jsonc
// Go
{ "name": "build", "type": "exit_code", "command": "go build ./...", "expect_code": 0 }
{ "name": "vet",   "type": "exit_code", "command": "go vet ./...",   "expect_code": 0 }

// Python
{ "name": "tests", "type": "exit_code", "command": "pytest -q", "expect_code": 0 }
{ "name": "types", "type": "exit_code", "command": "mypy src/",  "expect_code": 0 }

// React / TS
{ "name": "build",     "type": "exit_code", "command": "npm run build", "expect_code": 0 }
{ "name": "typecheck", "type": "exit_code", "command": "tsc --noEmit",  "expect_code": 0 }

// C++
{ "name": "build", "type": "exit_code", "command": "cmake --build build", "expect_code": 0 }
```

## 信任边界

`command` 经 `shell=True` 执行，等于「把 shell 命令写进配置」。**仅在你自己维护、完全信任的仓库自动跑**；审外部 PR / 不可信分支时，先人工确认配置内容再运行。
