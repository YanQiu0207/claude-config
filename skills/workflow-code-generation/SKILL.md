---
name: workflow-code-generation
description: 代码文件修改的统一入口。任何代码变更（新功能、优化、Bug 修复、重构）必须先调用此 skill。按复杂度路由：极轻改动主会话直接改，中等及以上下放 agent 执行（tasks.md 批准后自主连跑，worktree 隔离、每产物过 workflow-code-review + verify.py、末尾汇总 + intent 沉淀）。仅适用于代码文件（.cc/.cpp/.h/.go/.py 等），改 .md 等非代码文件不调用。
---

> 输出一行：`Using workflow-code-generation`

# 代码生成（统一执行入口）

**先加载规范再写代码。** 设计门（需求 / 设计 / tasks 批准）与质量基建（review + verify + intent 沉淀）不跳过，执行形态按复杂度路由——见下表。

## 执行形态总览

| 复杂度 | 执行形态 | 前置 |
| --- | --- | --- |
| **极轻**（单文件、局部、改一行级） | **Fast-Path**：主会话直接改 | 免 spec / tasks |
| **中等及以上**（多文件 / 多 task / 需设计） | **下放 agent 执行**，tasks 批准后自主连跑 | spec + tasks 批准 |

> 下放执行再分：**单 task / 串行依赖** → 单 agent 逐波；**多 task 无依赖** → 并行分波。同一套机制，只差波内并行度。

---

## 步骤 1：评估复杂度与路由

> ⚠️ **防御性检查**：无法明确回答「改什么文件」「实现什么行为」「怎样算完成」中任一个 → **立即停止**，调用 `workflow-requirements-clarification`。本 skill 不负责需求澄清。

- **极轻改动**（路由阶段就能确定完整文件列表，且只涉及 1 个文件的局部修改）→ **Fast-Path**。
- **其余一切**（多文件 / 需 spec / 可拆多 task）→ **标准流程**（下放 agent 执行）。
- **无法确定 → 标准流程。** Fast-Path 执行中发现外溢到多文件 → 立即退出，转标准流程。

---

## Fast-Path（极轻改动，主会话直接改）

主会话直接改，不起 agent / worktree。**不走 tasks.md 状态机 / 测试环 / 续跑那套**（那些是下放执行的机制），只做：

0. **采基线（仅当有 `verify.config.json`）**：动代码前加载 `workflow-verification`，`verify.py --save-baseline .verify/baseline.json`；无配置跳过。
1. 加载编码规范（同步骤 4）。
2. 实现改动。发现需改多个文件 → **立即退出**，转标准流程。
3. 询问是否需要 code review：需要 → `workflow-code-review`（`skip_reviewers: [magical-prompt-reviewer]`）+ 修复循环；不需要 → 跳过。
4. **门禁验证（仅当 `verify.config.json` 或 `.verify/baseline.json` 存在）**：加载 `workflow-verification`。Fast-Path 原地运行、不进 worktree，故用相对路径即可。
   - 有基线 → `verify.py --baseline .verify/baseline.json`（config 不存在时脚本报 ERROR）。
   - 仅有 config → `verify.py`。
   - 退出码 0 过；1（新增违规）修复后重跑；2（门禁故障）**停止交付**，排查 config / 工具 / 基线后再跑。**门禁通过前禁止汇报完成。**
5. **交付前沉淀检查**：见下方[「交付前沉淀检查」](#交付前沉淀检查)（强制，Fast-Path 不豁免）。
6. 输出改动说明（含沉淀判定结论），**结束**。

---

## 标准流程

### 步骤 2：查找 / 确认 spec

查找 `docs/design-docs/<module>/<feature>/spec.md`：
- 存在且完整 → **通读全文**（非只读关注章节），确认理解。
- `Quick Draft` 状态 → 检查是否含问题 / 目标 / 核心方案 / 关键接口 / 数据模型（如适用）/ 验收标准；满足则进入任务规划，否则调用 `workflow-quick-design` 补齐。
- 不存在 / 不完整 → **调用 `workflow-requirements-clarification`**（禁止自行澄清）。

**强制**：`spec.md` 与 `tasks.md` 同时存在时，编码前必须完整读取两者。

### 步骤 3：检查 / 创建 tasks.md

- **已存在** → 进入步骤 4。
- **不存在** → 先读 [reference/task_planning_guide.md](reference/task_planning_guide.md)，严格按其流程创建。每个 task 须带 `depends_on`、context（直接改文件 + 上游 + 下游）、可机械执行的验收标准——**`depends_on` 是分波并行的依据，必填**。

若本次改动可能涉及不可逆 / 高影响架构决策、放弃某方案或新增红线约束，加载 `project-knowledge`，预留一个「intent 沉淀」任务（步骤 6 收口）。

> 🚨 **创建 tasks.md 后必须停下等用户确认。** 展示任务列表（含依赖），**停止等待回复**。这是**人把关的最后一道闸**；批准后执行段自主连跑、不再逐 task 停。

### 步骤 4：加载编码规范（🚨 强制前置）

> **未加载规范就写代码 → 立即停止，先加载。** 下放 agent 时，把规范要点写进 prompt 或令其自行加载对应 skill。

| 规范 | 何时加载 |
| --- | --- |
| `bp-coding-best-practices` | 必须 |
| `bp-performance-optimization` | 必须（所有代码都性能敏感） |
| `std-cpp` / `std-go` / `std-python` | `.cc/.cpp/.h` / `.go` / `.py` 文件 |
| `bp-distributed-systems` | 网络通信 / 多节点协调 / 一致性 / 故障恢复 |

### 步骤 5：下放 agent 执行（🚨 批准后自主连跑）

tasks.md 经用户批准后，执行下放给 agent：**主会话只编排，不亲自写代码、不逐 task 停等**，全部跑完一次性汇总。

**先判定 CLI 嵌套能力**（派子 agent 试再派孙 agent；判定细则与 5 层上限见 reference 手册），选编排模式：
- **模式 A（默认，Claude Code 支持嵌套）**：每 task 派 owner 子 agent 自闭环——实现 → 内嵌测试 → 自跑 review → 自跑 verify → 有限轮次自修复，主 agent 只收集结论。
- **模式 B（兜底，不支持嵌套）**：implementer 只实现 + 写 / 跑测试，review / verify 由主 agent 对每个产物跑。

**详细操作（Phase 0 准备 / Phase 1 逐波执行 / 失败隔离 / 合并 / 阻塞）见 [reference/delegated-execution-guide.md](reference/delegated-execution-guide.md)，按其执行。** 核心不变量：每产物必过 review + verify 才合并；失败标 `需人工` 不阻塞其余；上游未合并则下游 `阻塞`；`tasks.md` 的 `状态:` 字段是续跑真相源。

### 步骤 6：功能交付与 intent 沉淀（🚨 强制，全部 task 完成后触发）

全部 wave 处理完、`tasks.md` 任务为 `完成` / `需人工` / `阻塞` 时，**禁止直接宣布交付**，先走：

1. **汇总报告**（一次性，不逐 task）：每个 task 的实现 / review / verify 结果，列出哪些 `需人工`（附原因）、哪些 `阻塞`（附上游归因，如「上游 Task N 未合并」）、哪些合并冲突。
2. **交付前沉淀检查**：见下方[「交付前沉淀检查」](#交付前沉淀检查)，并逐条核销步骤 3 / Phase 1 预留的「intent 沉淀」任务。
3. **归档**：按 `project-knowledge` 约定把 `spec.md` 头部 `状态` 改为 `Archived`（文件原地保留）。
4. 交付，等用户验收 `需人工` / `阻塞` 项的处理。

---

## 交付前沉淀检查

> 🚨 **Fast-Path 与步骤 6 共用 · 强制、与 verify 门禁无关**：无论是否存在 `verify.config.json` 都执行。

加载 `project-knowledge`，**逐条对照其沉淀检查信号表**（架构决策 / 放弃方案 / 新红线约束），每个信号逐行作答「命中 → 已沉淀到 <具体 ADR / spec 章节>」或「未命中」。**禁止用一句笼统的「无需沉淀」代替逐条判定。** 命中则写或更新 ADR 后再继续。**未给出逐条判定结论前，禁止宣布完成——沉默 = 未完成。** 判定需沉淀但当前无法完成 → 在 `tasks.md` 建「intent 沉淀」任务，不跳过。

---

## 🚨 强制规则

1. 极轻改动外，未经 spec + `tasks.md` 用户批准，**禁止**下放执行。
2. 有依赖的 task **禁止**同波并行；依赖缺失时保守串行或回问。
3. 每产物**必过** `workflow-code-review` + `verify.py`（若启用）才合并，不得跳过。
4. task 失败 / 冲突**必标** `需人工`（不得静默丢弃或假装通过），且不停其他 task；依赖它的后波**必标** `阻塞` 跳过 dispatch（上游合并后解阻）。
5. 收尾**必做** intent 沉淀检查并给逐条结论。
6. **测试与实现同批交付**（Fast-Path 除外）：接口层与核心逻辑须有覆盖关键路径、能跑通的测试，不允许先实现后补。
7. **进度表述校准**：「已查看」仅用于读取核对，「进行中」仅用于已 dispatch / 已改码，「已完成」仅用于已落地且已合并核对；禁止把「看过」说成「已开始」、把「想过」说成「在推进」。

## 用户跳过 spec 时

必须生成简化版 spec.md（标 `状态: Quick Draft`）。**禁止无 spec 修改中等+代码。** 该路径交付前同样受步骤 6 约束。

## 恢复中断

中断后按 `tasks.md` 的 `状态:` 字段定位续跑，详见 [reference/delegated-execution-guide.md](reference/delegated-execution-guide.md) 的「恢复中断」。**恢复路径不豁免步骤 6 的交付前沉淀检查。**

## 与其他 skill 的关系

本 skill 是所有代码修改的统一入口。`workflow-verification`（verify 门禁）、`workflow-code-review`（多维评审）、`project-knowledge`（intent 沉淀）是它调用的质量基建；`workflow-test-generation` 内嵌在每个 task 的执行流程中（实现后即写 / 跑测试，与实现同批）。设计阶段由 `workflow-requirements-clarification` / `workflow-system-design` / `workflow-quick-design` 承担。
