---
name: workflow-verification
description: 研发后机器验证门。有 verify.config.json 时配置驱动跑 build / test / lint 等客观检查 + 改动前后基线对比、只追新增违规；内置 spec drift 检查：改了代码但相关 spec.md / ui-spec.md / tasks.md / ADR 未更新时，必须提供无需更新原因。merge 前与 LLM review 并列的硬门。workflow-code-generation 实现后判定「是否真做完」，或用户要求跑验证时使用。
---

> 输出一行：`Using workflow-verification`

# 研发后机器验证门

把「完成」从 LLM 说了算变成机器绿灯。机器能验的不靠 LLM 背书。

## 两种模式

- **有 `verify.config.json`（大多数项目）** → 配置驱动，`scripts/verify.py` 跑 + 基线对比。
- **没有** → 只跑内置门禁；其余检查跳过。

## 内置 spec drift 检查

`verify.py` 总会检查本次 git diff：

- 改了代码文件，且无法证明相关 `spec.md` / `ui-spec.md` / `tasks.md` / ADR 已更新 → FAIL。
- 相关性只做机械判定：`tasks.md` 中出现代码路径，或代码文件位于同一规格目录下；判不出相关时必须传 `--spec-drift-reason "<原因>"`。
- 标准 / 下放流程必须在 Phase 0 记录 `base_sha`，后续验证显式传 `--diff-base <base_sha>`；禁止在已提交 / 已合并后的 clean 工作区裸用默认 `HEAD` 作为基准。
- 报告写入 `.verify/report.json` 的 `spec_drift` 字段，交付报告必须引用。

示例：

```bash
python <skill-dir>/scripts/verify.py \
  --spec-drift-reason "仅修复脚本输出编码，不改变需求、任务拆解或架构决策"
```

## 配置驱动

三类检查（config 的 `type` 字段）：

| type | 判定 | 用途 |
| --- | --- | --- |
| `exit_code` | 退出码 == `expect_code` | 编译必过、测试必过、自定义校验脚本 |
| `forbid_pattern` | 命中的每行算一处违规 | 静态规范：禁用 API / 语法 / 硬编码 |
| `count` | stdout 解析为数字按方向比 | 测试数不减少、文件不超长 |

`baseline_aware: true` 的检查参与基线对比，**只判超出基线的新增违规**（历史遗留不阻塞）。`forbid_pattern` 命令用 `-H` 保留文件路径、不带行号。

用法（`<skill-dir>` = 本 skill 安装目录）：

```bash
# 改动前采基线
python <skill-dir>/scripts/verify.py --save-baseline .verify/baseline.json
# 改动后验证并对比
python <skill-dir>/scripts/verify.py --baseline .verify/baseline.json
```

退出码：`0` 全过；`1` 有新增违规或 spec drift（进修复循环）；`2` 门禁自身出错（先排查配置）。

配置项目：`cp <skill-dir>/reference/verify.config.example.json verify.config.json`，按技术栈改 `command`；`.verify/` 加进 `.gitignore`。**怎么写配置、怎么接入自己的脚本见 [reference/config-guide.md](reference/config-guide.md)。**

## 执行规则

1. 改动所在 worktree、**review PASS 后**跑。
2. 全过（exit 0）→ 允许 merge。
3. **exit 1**（代码问题：编译错 / 测试挂 / 新增违规）→ 回实现改代码重跑，有限轮次仍 FAIL → 标 `需人工` + 附输出。**不停其他并行 task**。
4. **exit 2**（门禁自身坏了：工具缺失 / 正则非法 / 基线损坏）→ 改代码没用，直接标 `需人工` 排查配置 / 环境。
5. 无 config → 只跑内置门禁，汇报「未做项目自定义机器验证」。
6. `spec_drift` FAIL → 更新对应规格 / 任务 / ADR，或补 `--spec-drift-reason` 后重跑。

## 与 workflow-code-generation 集成

| 时机 | 动作 |
| --- | --- |
| 动代码前（Fast-Path / Phase 0） | 有 config → `--save-baseline` 采基线 |
| review PASS 后、merge 前 | 有 config → `--baseline <repo-root>/.verify/baseline.json --diff-base <base_sha>`；无 config → `--diff-base <base_sha>` |

> 下放执行在 worktree 内，基线须用**主仓库根绝对路径** `--baseline <repo-root>/.verify/baseline.json`（worktree 看不到未提交的基线）。
>
> **基线读多写一、并发安全**：`--save-baseline` 只在动代码前单点写一次，并行 task 验证时一律**只读对比**、不改基线；report 默认写各自 worktree 的 `.verify/report.json`（相对 cwd）。worktree 隔离是为了隔离代码改动，不是为了基线。

## 强制规则

| 规则 | 说明 |
| --- | --- |
| 客观优先 | 能机器判定的，不接受口头「应该没问题」 |
| 只追新增 | 基线下历史违规不阻塞，本次不得新增 |
| 文档同步 | 改代码但不改规格 / 任务 / ADR 时，必须写明无需更新原因 |
| 无侵入 | 无 config 时仅运行内置门禁，不跑项目自定义命令 |
| 不偷改 | 不得为过门删测试 / 放宽配置 |

## 信任边界

`command` 经 `shell=True` 执行，**仅自己信任的仓库自动跑**；审外部 PR / 不可信分支时先人工确认配置内容，不自动执行。
