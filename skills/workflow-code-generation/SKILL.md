---
name: workflow-code-generation
description: 代码文件修改的统一入口。任何代码变更（新功能、优化、Bug 修复、重构）必须先调用此 skill。按复杂度路由：轻量改动（请求即计划）主会话直接改，中等及以上下放 agent 执行（tasks.md 批准后自主连跑，worktree 隔离、每产物过分级 workflow-code-review、末尾汇总 + intent 沉淀）。仅适用于代码文件（.cc/.cpp/.h/.go/.py 等），改 .md 等非代码文件不调用。
---

> 输出一行：`Using workflow-code-generation`

# 代码生成（统一执行入口）

**先加载规范再写代码。** 设计门（需求 / 设计 / tasks 批准）与质量基建（review + intent 沉淀）不跳过，执行形态按复杂度路由——见下表。

前端分支由本地 `workflow-frontend-design` 定方向；本 skill 只消费其产出的 `ui-spec.md`，不维护外部前端技能选择表。

## 执行形态总览

| 复杂度 | 执行形态 | 前置 |
| --- | --- | --- |
| **轻量**（请求即计划的局部低风险修改） | **Fast-Path**：主会话直接改 | 免 spec / tasks |
| **中等及以上**（超出轻量判据 / 需设计 / 可拆多 task） | **下放 agent 执行**，tasks 批准后自主连跑 | spec + tasks 批准 |

> 下放执行再分：**单 task / 串行依赖** → 单 agent 逐波；**多 task 无依赖** → 并行分波。同一套机制，只差波内并行度。

---

## 步骤 1：评估复杂度与路由

> ⚠️ **防御性检查**：无法明确回答「实现什么行为」「怎样算完成」中任一个 → **立即停止**，调用 `workflow-requirements-clarification`。需求和验收标准清楚、但尚不能确定文件或实现方案，不等于需求不清；按下方规则进入 `workflow-quick-design`。

- **轻量改动** → **Fast-Path**。核心判据是**请求即计划**：用户请求本身已完整确定改什么、怎么改，AI 无需替用户做任何未言明的设计决策。在此前提下须全部满足：路由阶段就能确定完整文件列表；每处修改是局部的（不改函数签名 / 模块边界 / 公开接口）；不碰数据 / 权限 / 并发 / 安全 / 性能关键路径。文件数只作护栏不作主判据：超过 3 个文件默认不走 Fast-Path，除非是同一模式的机械重复（如统一改名、同一防护补丁多点应用）。机械重复是指每处应用相同变换，不改变接口、契约、控制流或模块交互。Fast-Path 固定使用 `lightweight` 档，由单个综合 reviewer 覆盖工程规范、需求符合度、正确性与健壮性。
- **需求与验收标准清楚，但需要补实现方案或文件定位** → 直接调用 `workflow-quick-design`，不先走需求澄清。若 Quick Design 识别出安全、权限、数据迁移、并发、分布式、性能关键路径、公共 API 或大范围重构，再升级为完整需求与系统设计流程。
- **需求或验收标准不清楚** → 调用 `workflow-requirements-clarification`。
- **其余一切**（已有 spec / tasks，或 Quick Design 完成）→ **标准流程**（下放 agent 执行）。
- **无法确定 → 标准流程。** Fast-Path 执行中发现外溢（文件列表超出路由判断，或触碰高风险面）→ 立即退出，转标准流程。

---

## Fast-Path（轻量改动，主会话直接改）

主会话直接改，不起 agent / worktree。**不走 tasks.md 状态机 / 测试环 / 续跑那套**（那些是下放执行的机制），只做：

1. 加载编码规范（同步骤 4）。
2. 实现改动（动代码前若有 `verify.config.json`，先 `workflow-verification` 采基线；**无 config → 暂停**，提示用户先运行 `/verify-config` 初始化，用户明确跳过才继续，只跑内置门禁并在交付报告标注）。发现外溢（超出步骤 1 路由判据）→ **立即退出**，转标准流程。
3. **自动运行 code review**：加载 `workflow-code-review`（`review_profile: lightweight`）。结论为 `NEEDS_CHANGES`（存在 keep 的 P0 / P1）→ 自行修复后按其**复审模式**重跑，最多 2 轮复审；仍 `NEEDS_CHANGES` → 标「需人工」，附 finding 摘要终止交付。**P2 / follow-up 不触发修复循环**，原样记入交付报告。
4. **机器验证**：加载 `workflow-verification`（有 config 比基线；无 config 也跑内置 spec drift 检查），绿才继续；失败回第 2 步修复，若只是无法证明相关规格已更新且确实无需更新，则补 `--spec-drift-reason` 后重跑。
5. **前端验证**：若涉及 UI / 样式 / `.tsx` / 用户操作路径，加载 `bp-frontend-taste` 后再用 `frontend-playwright-verification` 做浏览器验证。若验证阶段产生代码改动，必须回到第 3 步重跑 code review（复审模式，范围为本次新增改动）。
6. **交付前沉淀检查**：见下方[「交付前沉淀检查」](#交付前沉淀检查)（强制，Fast-Path 不豁免）。
7. **提交**：将本次改动提交本地 git（push / `svn commit` 由用户决定）；用户明确要求不提交时，在交付报告标注「未提交待用户处理」。
8. **交付门（机器判定）**：跑 `python <本 skill 目录>/scripts/check_delivery.py`（免 spec / tasks，只校验工作区干净）。非 0 → 补提交后重跑；用户要求不提交的改动是唯一豁免，在报告中标注。
9. 按[「统一交付证据格式」](#统一交付证据格式)输出改动说明，**结束**。

---

## 标准流程

### 步骤 2：查找 / 确认 spec

查找 `docs/design-docs/<module>/<feature>/spec.md`，**完整性由脚本判定，不由 AI 自述**：跑 `python <本 skill 目录>/scripts/lint_spec.py <spec.md> --phase code`（Quick Draft 自动按简化章节校验）。
- 通过 → **通读全文**（非只读关注章节），确认理解。
- 未通过 → 按缺失位置路由：1～3 章缺失或占位 → **调用 `workflow-requirements-clarification`**（禁止自行澄清）；第 4 章缺失或占位 → 调用 `workflow-system-design`；Quick Draft 缺节 → 调用 `workflow-quick-design` 补齐。
- 不存在 → 调用 `workflow-requirements-clarification`。

**强制**：`spec.md` 与 `tasks.md` 同时存在时，编码前必须完整读取两者。

**前端分支检查**：任务涉及 `.tsx` 文件或 UI 页面时：
- 同目录下存在 `ui-spec.md` → 与 `spec.md` 一起**强制通读**，`ui-spec.md` 是视觉与布局契约，代码实现须与其对齐。
- 同目录下不存在 `ui-spec.md` → **立即停止**，提示用户先运行 `/frontend-design` 生成视觉方案，再回到本工作流。

### 步骤 3：检查 / 创建 tasks.md

- **已存在** → 进入步骤 4。
- **不存在** → 先读 [reference/task_planning_guide.md](reference/task_planning_guide.md)，严格按其流程创建。每个 task 须带 `depends_on`、`review_profile`、`context_files`、`verification`、`artifacts`——**`depends_on` 是分波并行的依据，`review_profile` 是分级 review 的依据，均必填**。

若本次改动可能涉及不可逆 / 高影响架构决策、放弃某方案或新增红线约束，加载 `project-knowledge`，预留一个「intent 沉淀」任务（步骤 6 收口）。

**前端任务闭环**：若本次涉及 UI / 样式 / `.tsx` / 用户操作路径，`tasks.md` 必须包含：
- 实现任务：按 `ui-spec.md` 实现页面 / 组件。
- 测试任务：通过 `workflow-test-generation` 生成或补齐关键交互 / 状态测试。
- 最终验证任务：执行 `bp-frontend-taste` 和 `frontend-playwright-verification`，失败则回到实现任务修复。

> 🚨 **创建 tasks.md 后必须停下等用户确认。** 展示任务列表（含依赖），**停止等待回复**。这是**人把关的最后一道闸**；批准后执行段自主连跑、不再逐 task 停。确认时若项目根无 `verify.config.json`，一并提示先运行 `/verify-config` 初始化或明确跳过（跳过则本次只跑内置门禁并在交付报告标注）；代码任务全程不修改该配置。

### 步骤 4：加载编码规范（🚨 强制前置）

> **未加载规范就写代码 → 立即停止，先加载。** 下放 agent 时，把规范要点写进 prompt 或令其自行加载对应 skill。

| 规范 | 何时加载 |
| --- | --- |
| `bp-coding-best-practices` | 必须 |
| `bp-performance-optimization` | 必须（所有代码都性能敏感） |
| `std-cpp` / `std-go` / `std-python` | `.cc/.cpp/.h` / `.go` / `.py` 文件 |
| `std-react` | `.tsx` / `.ts` 前端文件；默认用 shadcn/ui 写基础组件 |
| `bp-frontend-layout` | 新页面、页面重排、导航结构、响应式骨架 |
| `bp-frontend-taste` | 可见 UI 实现完成后的收尾质检 |
| `bp-distributed-systems` | 网络通信 / 多节点协调 / 一致性 / 故障恢复 |
| `bp-cola-ddd` | spec.md 或目录结构显示 DDD 分层（adapter / domain / application / infrastructure）、多外部依赖或业务规则较复杂时加载 |

### 步骤 5：下放 agent 执行（🚨 批准后自主连跑）

tasks.md 经用户批准后，执行下放给 agent：**主会话只编排，不亲自写代码、不逐 task 停等**，全部跑完一次性汇总。

**先为每个 task 判定 review 档位**：

| 档位 | 适用 |
| --- | --- |
| `lightweight` | 小需求 / 低风险：局部改动，或不改变接口、契约、控制流与模块交互的跨文件机械重复改动；不碰数据 / 权限 / 并发 / 安全 / 性能关键路径 |
| `standard` | 默认档：普通功能、Bug 修复，或涉及多个模块之间的行为、契约、交互变化但风险可控 |
| `strict` | 高风险：生产关键路径、安全 / 权限 / 数据迁移 / 并发 / 分布式 / 性能敏感 / 公共 API / 大范围重构 |

无法判断风险时选 `standard`；命中高风险任一条件时选 `strict`。各档位对应的 reviewer 集由 `workflow-code-review` 定义（本 skill 只判档，不重列）。review 档位写入 task context，owner / implementer 必须按档位调用 `workflow-code-review`。

**主会话必须通过控制流内核构建波次（wave）数组**：先运行 `python <本 skill 目录>/scripts/workflow_control.py <tasks.md 路径> waves` 得到任务 ID 分层数组，按 [reference/delegated-execution-guide.md](reference/delegated-execution-guide.md) 将当前一波的每个任务 ID 富化为 task 对象（从 `tasks.md` 取 `title`、`context_files`、`verification`、`artifacts`、`review_profile`）后再传入 Workflow 工具的 `args.waves`。每波 dispatch 前运行同一脚本的 `dispatchable`，只执行输出的 task。缺 `depends_on` 时先由 `lint_task_deps.py` 报错，修复前禁止全并行。**禁止另写一套手工分波或状态判断**。

**先判定 CLI 嵌套能力**（派子 agent 试再派孙 agent；判定细则与 5 层上限见 reference 手册），选编排模式：
- **模式 A（默认，Claude Code 支持嵌套）**：每 task 派 owner 子 agent 执行实现、测试和机器验证。`lightweight` / `standard` 由 owner 自跑 review；`strict` 由主 agent 或独立 Judge Agent 调用 `workflow-code-review` 并裁决，owner 只接收 keep finding 并修复。
- **模式 B（兜底，不支持嵌套）**：implementer 只实现 + 写 / 跑测试，review 由主 agent 对每个产物跑。

**详细操作（Phase 0 准备 / Phase 1 逐波执行 / 失败隔离 / 合并 / 阻塞）见 [reference/delegated-execution-guide.md](reference/delegated-execution-guide.md)，按其执行。** 核心不变量：每产物必过 review **且过 `workflow-verification` 机器验证（build / test 等检查全绿）** 才合并；失败标 `需人工` 不阻塞其余；上游未合并则下游 `阻塞`；`tasks.md` 的 `状态:` 字段是续跑真相源。Claude Code 使用 `Workflow` 工具替代 `Agent` 工具以规避主会话上下文膨胀，详见上方 reference 手册。

### 步骤 6：功能交付与 intent 沉淀（🚨 强制，全部 task 完成后触发）

全部 wave 处理完、`tasks.md` 任务为 `完成` / `需人工` / `阻塞` 时，**禁止直接宣布交付**，先走：

1. **汇总报告**（一次性，不逐 task）：每个 task 的实现 / review 结果，列出哪些 `需人工`（附原因）、哪些 `阻塞`（附上游归因，如「上游 Task N 未合并」）、哪些合并冲突。
2. **最终审核**：仅当本次包含 2 个及以上已合并 task 时，对所有变更文件整体调用 `workflow-code-review`（`review_profile` 取各 task 中最高档位），聚焦跨 task 的集成问题。只有 1 个 task 时，task 级 Review 已覆盖全部改动，跳过重复的整体 Review；若合并后又产生 task Review 未覆盖的代码改动，则仍须执行最终 Review。最终 Review 为 `NEEDS_CHANGES`（存在 keep 的 P0 / P1）→ **派 fix agent 修复后按复审模式重审**（主会话只编排，不亲自写代码），最多 2 轮；仍 `NEEDS_CHANGES` → 整体标 `需人工`，附 Review Finding 摘要，终止循环。**P2 / follow-up 不触发修复循环**，记入汇总报告。
3. **机器验证**：对合并结果整体跑 `workflow-verification`。有 config 时必须传 `--baseline <repo-root>/.verify/baseline.json --diff-base <base_sha>`；无 config 时必须传 `--diff-base <base_sha>` 触发内置 spec drift 检查。FAIL → 派 fix agent 修复后回第 2 步重审（复审模式，范围为修复 diff）再验，若只是无法证明相关规格已更新且确实无需更新，则补 `--spec-drift-reason` 后重跑；仍 FAIL 标 `需人工`；未验到列为风险。
4. **前端验证**：若涉及 UI / 样式 / `.tsx` / 用户操作路径，加载 `bp-frontend-taste` 后再用 `frontend-playwright-verification` 做浏览器验证。失败则修复后重跑；若修复产生代码改动，必须回到第 2 步重新最终审核（复审模式，范围为本次新增改动），再重新验证。无法验证则列为风险。
5. **交付前沉淀检查**：见下方[「交付前沉淀检查」](#交付前沉淀检查)，并逐条核销步骤 3 / Phase 1 预留的「intent 沉淀」任务。
6. **归档**：按 `project-knowledge` 约定把 `spec.md` 头部 `状态` 改为 `Archived`（文件原地保留）。
7. **提交归档产物**：将工作区本次残留的全部改动（fix 修复、spec / tasks / ADR / issues 等文档）提交本地 git，提交信息关联 feature，交付时工作区必须干净；push / `svn commit` 仍由用户决定。
8. **交付门（机器判定）**：跑 `python <本 skill 目录>/scripts/check_delivery.py --tasks <tasks.md> --spec <spec.md>`——校验任务全部终态且附原因、spec 已归档、工作区干净。非 0 → 回对应步骤修复后重跑；输出原样贴进交付报告。
9. 按[「统一交付证据格式」](#统一交付证据格式)交付，等用户验收 `需人工` / `阻塞` 项的处理。

## 统一交付证据格式

最终报告必须包含：

```markdown
## 任务归因
- **Feature**: [feature 标识]
- **Task**: [Task ID/名称]
- **Review Profile**: lightweight / standard / strict
- **Review Retries**: [非负整数]
- **Verify Retries**: [非负整数]
- **Manual Intervention**: 无 / [介入阶段，多个位置用中文逗号分隔]
```

每个 task 输出一个完整区块；同一 task 再次交付时重新输出完整区块。字段名和标题是遥测解析接口，不得改写或省略，不得从对话推测未知值。

- **改动文件**：列出代码、规格、任务、ADR 和关键文档。
- **提交状态**：本地 commit hash（代码与归档产物），或「未提交待用户处理」及原因。
- **交付门**：`check_delivery.py` 输出（各项 PASS，或未过项及处理说明）。
- **测试命令**：列出实际运行命令、结果；未运行写原因。
- **review 结论**：列出 review_profile、通过 / finding / 需人工。
- **机器验证**：列出 `workflow-verification` 结果和 `.verify/report.json` 路径；必须包含 `spec_drift` 结论；注明配置消费状态（使用现有 / 缺失已跳过 / 建议刷新及原因——如 exit 2 或配置引用的命令、路径失效，提示用户之后运行 `/verify-config`，不在任务内改配置）。
- **前端截图 / DOM 验证**：涉及 UI 时列截图路径、DOM / console / 交互检查；不涉及写「不涉及」。
- **未验证风险**：列出无法验证项、阻塞原因和建议补验方式。

---

## 交付前沉淀检查

> 🚨 **Fast-Path 与步骤 6 共用 · 强制**：

加载 `project-knowledge`，**逐条对照其沉淀检查信号表**（架构决策 / 放弃方案 / 新红线约束），每个信号逐行作答「命中 → 已沉淀到 <具体 ADR / spec 章节>」或「未命中」。**禁止用一句笼统的「无需沉淀」代替逐条判定。** 命中则写或更新 ADR 后再继续。**未给出逐条判定结论前，禁止宣布完成——沉默 = 未完成。** 判定需沉淀但当前无法完成 → 在 `tasks.md` 建「intent 沉淀」任务，不跳过。

---

## 🚨 强制规则

1. 轻量改动外，未经 spec + `tasks.md` 用户批准，**禁止**下放执行。*例外：由 `workflow-quick-design` 自动 pipeline 调用时，spec 用户确认已视为 tasks.md 预授权，本规则不触发。*
2. 有依赖的 task **禁止**同波并行；依赖缺失时保守串行或回问。
3. 每产物**必过匹配风险档位的** `workflow-code-review` 才合并，中等及以上任务不得整体跳过 review。
4. task 失败 / 冲突**必标** `需人工`（不得静默丢弃或假装通过），且不停其他 task；依赖它的后波**必标** `阻塞` 跳过 dispatch（上游合并后解阻）。
5. 收尾**必做** intent 沉淀检查并给逐条结论。
6. **测试与实现同批交付**（Fast-Path 除外）：接口层与核心逻辑须有覆盖关键路径、能跑通的测试，不允许先实现后补。
7. **进度表述校准**：「已查看」仅用于读取核对，「进行中」仅用于已 dispatch / 已改码，「已完成」仅用于已落地且已合并核对；禁止把「看过」说成「已开始」、把「想过」说成「在推进」。

## 用户跳过 spec 时

必须生成简化版 spec.md（标 `状态: Quick Draft`）。**禁止无 spec 修改中等+代码。** 该路径交付前同样受步骤 6 约束。

## 恢复中断

中断后先收集已合并任务 ID，再运行 `python <本 skill 目录>/scripts/workflow_control.py <tasks.md 路径> recover --merged <任务 ID...>` 生成恢复计划；按计划核对 worktree 和质量门，详见 [reference/delegated-execution-guide.md](reference/delegated-execution-guide.md) 的「恢复中断」。**恢复路径不豁免步骤 6 的交付前沉淀检查。**

## 与其他 skill 的关系

本 skill 是所有代码修改的统一入口。`workflow-code-review`（分级评审）、`project-knowledge`（intent 沉淀）是它调用的质量基建；`workflow-test-generation` 内嵌在每个 task 的执行流程中（实现后即写 / 跑测试，与实现同批）。设计阶段由 `workflow-requirements-clarification` / `workflow-system-design` / `workflow-quick-design` 承担。
