---
name: workflow-verification
description: 研发后验证门禁。对代码改动跑可配置的客观检查（静态规范、编译/测试通过、计数类指标），支持改动前后基线对比，只追究新增违规。当 workflow-code-generation 完成实现需要客观判定「是否真的做完」，或用户要求跑门禁/验证时使用。
---

> 输出一行：`Using workflow-verification`

# 研发后验证门禁

> 把「完成」从「我觉得做完了」变成「脚本判定通过才算做完」。

## 核心定位

Rule 是软约束（会被忽略、绕过、解释性执行）；**能机械判定的约束应下沉为可执行门禁**。本 skill 提供一个配置驱动的验证器 `scripts/verify.py`，对改动做客观检查，并通过**基线对比**只追究本次新增的违规——堵住「这是历史遗留、不是我引入的」这类口头辩解。

## 信任边界说明

> ⚠️ `verify.config.json` 中的 `command` 字段会被 `shell=True` 直接执行，本质上是「把 shell 命令写进配置」。**此工具仅适用于你自己维护、完全信任的项目仓库**；在审查外部 PR 或不可信分支时，切勿自动执行门禁——应先人工确认配置内容无异常后再运行。

verify.py 通过以下措施降低风险：
- Schema 校验拒绝格式异常的配置文件。
- Check 指纹校验检测基线采集后的配置变更。
- 每个命令有超时上限（默认 60s，可通过 `timeout_seconds` 覆盖）。

## 前提：项目根的 verify.config.json

门禁是**可选**的、对存量项目无侵入：

- 项目根**存在** `verify.config.json` → 按其定义跑检查。
- **不存在** → 门禁自动跳过（脚本退出码 0），流程照常。

## 三类检查（对应配置 type 字段）

| type | 判定方式 | 典型用途 |
|------|---------|---------|
| `exit_code` | 命令退出码 == `expect_code`（默认 0） | 编译必过、测试必过、自定义校验脚本 |
| `forbid_pattern` | 命令 stdout 命中的每一行视为一处违规 | 静态规范：禁用 API、硬编码文案、禁用语法 |
| `count` | 解析命令 stdout 为数字，按 `direction` 与基线比 | 测试数量不减少、文件不超长 |

`baseline_aware: true` 的检查参与基线对比：

- `forbid_pattern`：按**出现次数**与基线比对，只对**超出基线的新增命中**判 fail（同名重复命中也能逐个识别，不会因去重而漏判）。
- `count`：`direction: not_decrease`（current ≥ baseline）或 `not_increase`（current ≤ baseline）。

> ⚠️ `forbid_pattern` 的命令必须用 **`-H`（保留文件路径）**，不用 `-h`；输出格式为「文件:匹配内容」而非单纯匹配文本，确保跨文件移动（删旧增新同名违规）可被识别。同时**不输出行号**，避免行号漂移把历史违规误判为新增。示例：`grep -rHo --include=*.cs "pattern" src/`。
>
> ⚠️ **已知限制**：`forbid_pattern` 基线对比基于「全量扫描结果的出现次数差」。若同一文件删除一处旧违规、同时新增一处相同模式的违规（如同文件内移位），两次出现次数相同，门禁会判为 PASS。如需检测这类"等量替换"场景，应在 command 中使用含行号的输出（`grep -rHn`）并接受行号漂移带来的误报，或改用 diff-aware 的外部工具。

## 用法

> 下方 `<skill-dir>` 指本 skill 的**实际安装目录**（执行时替换为真实路径）：在框架仓库内即 `skills/workflow-verification`，作为已安装 skill 时为其安装目录（如 `.claude/skills/workflow-verification`）。脚本仅依赖 Python 3 标准库；cwd 应为被检查的项目根（`verify.config.json` 所在处）。

```bash
# 改动前：采集基线（只跑 baseline_aware 的检查，存其"值"）
python <skill-dir>/scripts/verify.py --save-baseline .verify/baseline.json

# 改动后：验证并与基线对比，产出 .verify/report.json
python <skill-dir>/scripts/verify.py --baseline .verify/baseline.json

# 不带基线：所有检查按绝对标准判定
python <skill-dir>/scripts/verify.py
```

退出码：`0` 全过 / 无配置；`1` 存在（新增）违规（verdict=FAIL）；`2` 门禁本身出错——工具缺失、正则非法、基线损坏等（verdict=ERROR）。`1` 和 `2` 严格区分：`1` 应进入修复循环，`2` 应先排查门禁配置本身。

> 采集基线时，若某个 baseline_aware 检查的命令本身执行失败（工具缺失、正则非法、缺字段等），脚本以退出码 `2` 中止，**不写入伪基线**——避免后续对比基于一份无效基线而失真。`forbid_pattern` 记录到的"已存在违规"不算失败，会照常写入基线。

## 与 workflow-code-generation 集成

| 时机 | 动作 |
|------|------|
| 动代码前（Fast-Path 步骤 0 / 下放执行 Phase 0） | `--save-baseline` 采集基线 |
| review PASS 后（Fast-Path 4.5 / 下放执行 Phase 1 质量门） | `--baseline` 验证；FAIL 回修复循环，PASS 才汇报 |

> 下放执行在 git worktree 内运行，基线须用**主仓库根绝对路径** `--baseline <repo-root>/.verify/baseline.json`（worktree 看不到未提交的基线，否则对比被静默跳过）；绝对路径不可达按门禁故障（ERROR）处理。详见 `workflow-code-generation` 步骤 5。

## 配置项目自己的检查

复制示例并按技术栈改 `command`：

```bash
cp <skill-dir>/reference/verify.config.example.json verify.config.json
```

`command` 由项目按其所在平台与技术栈编写（脚本用 shell 执行命令字符串）。`.verify/` 建议加入 `.gitignore`（基线与报告是本地临时产物）。

## 强制规则

| 规则 | 说明 |
|------|------|
| 客观优先 | 能脚本判定的，不接受口头「应该没问题」 |
| 只追新增 | 基线对比下，历史违规不阻塞，但本次不得新增 |
| 无侵入 | 无 `verify.config.json` 时静默跳过，不报错 |
| 不偷改 | 不得为过门禁而删测试 / 放宽配置（`count` + `not_decrease` 正是为此） |

## 参考资料

- [配置示例](reference/verify.config.example.json)
