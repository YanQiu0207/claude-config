# 下放 agent 执行指南

> 本手册承接 `workflow-code-generation` SKILL 步骤 5：tasks.md 批准后的下放执行细则。单 task = 1 波 1 agent，多 task 无依赖 = 并行分波。

## 编排模型：先判定 CLI 嵌套能力

`workflow-code-review` 会按 task 风险派轻量 / 标准 / 严格 reviewer 集。**子 agent 能否再派子 agent**（嵌套 dispatch）决定 review / verify 跑在哪层。

- **实测**：派一个子 agent，让它再派一个孙 agent 回一句话；成功即支持。
- Claude Code **支持**嵌套（版本号与来源见框架根 `docs/03-parallel-execution-mode.md`，可能随 CLI 更新而变）；**最终以实测为准**。
- ⚠️ **嵌套深度上限 5 层**（固定、不可配置；第 5 层子 agent 不再获得 `Agent` 工具）。模式 A 的 `lightweight` / `standard` 链深 3 层（主 agent → owner → reviewer）；`strict` 的 reviewer 由独立 Judge 派发，owner 不在 review 调用链中。

| 模式 | 适用 | owner / implementer 职责 | 质量门跑在哪 |
| --- | --- | --- | --- |
| **A（默认）** | 支持嵌套（Claude Code） | owner 完成实现、测试和机器验证；`lightweight` / `standard` 自跑 review，`strict` 只接收独立 Judge 的 keep finding 并修复 | `lightweight` / `standard` 在 owner 内；`strict` 在主 agent 或独立 Judge Agent 内 |
| **B（兜底）** | 不支持嵌套（其他 CLI） | implementer 只实现 + 写 / 跑测试 | 主 agent 对每个产物跑 |

两模式只差「质量门跑在哪层」，其余流程一致。无论采用哪种模式，`strict` 的 implementer、reviewer、Judge 都不得是同一执行主体。

## Claude Code 专属：Workflow 工具编排（推荐，规避主会话上下文膨胀）

模式 A 用 `Agent` 工具派 owner agent，子 agent 的全部输出追加到主会话上下文，长程任务容易撑爆。**Claude Code 改用 `Workflow` 工具**——脚本后台运行，完成后只返回最终报告，主上下文不膨胀。

**主会话操作**：先运行 `waves` 获得结构波次，再运行 `dispatchable` 选择当前可执行 task。每次只把当前一波包装成单元素 `args.waves` 调用 `Workflow`；该波结果写回并执行 `block --write` 后，重新运行 `dispatchable` 决定下一波：

```javascript
export const meta = {
  name: 'code-gen-waves',
  description: '按波次并行执行代码生成任务',
  phases: [{ title: '执行' }, { title: '汇总' }],
}

const RESULT_SCHEMA = {
  type: 'object',
  required: ['taskId', 'status', 'summary', 'independent_review_required', 'verify_command', 'verify_report_path', 'spec_drift'],
  properties: {
    taskId:             { type: 'string' },
    status:             { type: 'string', enum: ['完成', '待评审', '需人工', '阻塞'] },
    summary:            { type: 'string' },
    independent_review_required: { type: 'boolean' },
    verify_command:     { type: 'string' },
    verify_report_path: { type: 'string' },
    spec_drift:         { type: 'string' },
    issues:             { type: 'array', items: { type: 'string' } },
  },
}

// args.base_sha: Phase 0 记录的 git rev-parse HEAD
// args.baseline_path: 有 verify.config.json 时为 <repo-root>/.verify/baseline.json；无 config 时为空
// args.waves: 仅含当前可执行波 [[{ id, title, context_files, verification, artifacts, review_profile }, ...]]
// 单次 Workflow 只执行一波；主会话写回状态后再启动下一波
const allResults = []
for (const wave of args.waves) {
  phase('执行')
  const waveResults = await parallel(wave.map(task => () =>
    agent(
      `你是 ${task.id} 的 owner agent。\n` +
      `任务：${task.title}\nReview 档位：${task.review_profile}\nContext：${task.context_files}\n验证：${task.verification}\n产物：${task.artifacts}\n\n` +
      `完成后依次执行：\n` +
      `1. 确认所有子任务已完成；测试子任务须已调用 workflow-test-generation 生成并运行通过\n` +
      `2. review_profile 为 lightweight / standard：加载 workflow-code-review；结论 NEEDS_CHANGES（keep 的 P0/P1）→ 修复后按复审模式重跑，最多 2 轮，仍不过标「需人工」；review_profile 为 strict：不得调用 workflow-code-review 或裁决，返回 status=待评审、independent_review_required=true\n` +
      `3. 加载 workflow-verification 跑机器验证；有 config 必须传 --baseline ${args.baseline_path} --diff-base ${args.base_sha}，无 config 必须传 --diff-base ${args.base_sha}；FAIL 则修复重跑；lightweight / standard 修复产生代码 diff 时，须按复审模式（范围为该 diff）重过 review 再验\n` +
      `4. 返回 independent_review_required、verify_command、verify_report_path、spec_drift 结论；不输出完整 diff`,
      { label: task.id, phase: '执行', schema: RESULT_SCHEMA, isolation: 'worktree' }
    )
  ))
  allResults.push(...waveResults.filter(Boolean))
}

phase('汇总')
return { results: allResults }
```

Workflow 完成后，主会话拿到 `results` 数组。所有 task 先通过 `event quality_passed` 进入待合并决策；只有 Git 合并成功后才能通过 `event merge_success` 标为「完成」。`independent_review_required=true` 时，先由主 agent 或独立 Judge Agent 完成 `strict` review，把 keep finding 交给 owner 修复并按复审模式重审。

> **与 Phase 1 的关系**：本方案替代 Phase 1 中「主会话用 `Agent` 工具 dispatch」的部分；失败隔离与合并规则保持一致。`strict` 的 review、裁决和最终状态写回由主会话负责，owner 不参与。

## Phase 0：准备

1. **加载编码规范**（步骤 4 已做）。
2. **记录 diff 基准**：动代码前记录 `base_sha=$(git rev-parse HEAD)`；后续所有 worktree 与最终验证都显式传 `--diff-base <base_sha>`，避免提交 / 合并后工作区 clean 导致 spec drift 误判无改动。
3. **采机器验证基线**：若项目根有 `verify.config.json`，在动代码前 `python <skill-dir>/scripts/verify.py --save-baseline <repo-root>/.verify/baseline.json`，并把该绝对路径作为 `baseline_path` 传入 Workflow；无 config 时 `baseline_path` 为空（走到这里意味着用户已在 tasks.md 批准闸口明确跳过 `/verify-config` 初始化）。基线采集后本次任务冻结 `verify.config.json`，不得修改。
4. **校验依赖**：跑 `python <本 skill 目录>/scripts/lint_task_deps.py <tasks.md 路径>` 检查 dangling 依赖、循环依赖、「改同一文件却无依赖关系」的并行冲突，以及必填字段完整性。有 ERROR 必须先修；有 WARN（潜在并行冲突）逐条确认是补 `depends_on` 还是确属可并行。
5. **构建依赖波（wave）并传入 Workflow**：运行以下命令，使用输出的稳定拓扑波次数组作为 `args.waves`。禁止手工维护另一套分波逻辑。

   ```bash
   python <本 skill 目录>/scripts/workflow_control.py <tasks.md 路径> waves
   ```

   每波 dispatch 前再运行 `dispatchable`，只派发输出的「未开始且依赖全部完成」任务。单次 Workflow 只接收当前一波；该波写回状态并传播阻塞后，主会话再次运行此命令：

   ```bash
   python <本 skill 目录>/scripts/workflow_control.py <tasks.md 路径> dispatchable
   ```

   缺少 `depends_on` 或依赖非法时，先修复 `lint_task_deps.py` 报错，**禁止对未知依赖全并行**。单 task 即单波。

## Phase 1：逐波执行（波内并行，波间串行）

> 🗂 **`tasks.md` 是进度真相源**：每个 task 的 `状态:` 字段实时写回（`未开始` / `进行中` / `完成` / `需人工` / `阻塞`）——dispatch 标 `进行中`，合并成功标 `完成`，失败 / 冲突标 `需人工`（附原因 + 失败输出），上游未合并的下游标 `阻塞`。每步完成即更新，中断后靠它续跑。

对每个 wave：

1. **dispatch**：波内每个 task 派一个子 agent（A 为 owner、B 为 implementer），各自在隔离 git worktree（基于当前分支 HEAD）工作，受并发上限约束、超出排队。多个子 agent **在同一条消息里并行派发**。
   - worktree：用 Agent 工具的 `isolation: "worktree"`，或 `git worktree add -b <task-branch> <path> HEAD`。
   - prompt 公共部分：task 描述 + `context_files`（直接改文件 + 上游 + 下游）+ `verification` + `artifacts` + `spec` / `tasks` 摘要 + 编码规范要点 + worktree 路径 + 「只在此 worktree 内改、改完提交」。
   - 职责见上方编排模型表（A 按 review 档位分流 / B 只实现 + 测试）。**测试与实现同批**：接口层与核心逻辑必须有覆盖关键路径、能跑通的测试，不允许先实现后补。
2. **质量门**（review + 机器验证，两者都过才算通过）：
   - 模式 A：`lightweight` / `standard` 由 owner 跑 review 与 `workflow-verification`，主 agent 只收集结论；`strict` 由 owner 跑 `workflow-verification`，主 agent 或独立 Judge Agent 跑 review 并裁决。
   - 模式 B：主 agent 对每个产物（在其 worktree 内）扮演 `workflow-code-review` 的 Judge 按 `review_profile` 裁决，再跑 `workflow-verification` 机器验证。
3. **失败隔离**：测试 / review（结论 `NEEDS_CHANGES`）/ 机器验证任一不过 → 有限轮次（≤ 2）自修复重跑。review 重跑用复审模式；模式 A 的 `lightweight` / `standard` 在 owner 内修复，`strict` 由独立 Judge 把 keep finding 交给 owner 修复后复审；模式 B 由主 agent 派 fixer 在同一 worktree 修。仍不过、或子 agent 报范围 / 依赖问题无法在本 task 内解决 → 标 `需人工` 附原因 + 失败输出（review finding / 错误摘要）；**子 agent 崩溃 / 超时 / 无产物返回** → 标 `需人工` 注「agent 未返回，需重 dispatch」。标 `需人工` 的 task **其 worktree 保留**供排查、不清理。以上**均不阻塞同波其他 task、不停整个流程**。 任务结果必须交给控制流内核裁决并写回，不得凭 Prompt 自行判断重试耗尽：

   ```bash
   python <本 skill 目录>/scripts/workflow_control.py <tasks.md 路径> event <任务 ID> failure --max-attempts 2 --reason "<失败摘要>" --write
   ```

   dispatch 前调用 `event <任务 ID> start --write`，脚本会再次校验所有依赖均为「完成」；质量门通过后调用 `event <任务 ID> quality_passed --write`，此时状态仍为「进行中」，但 `control_stage` 持久化为 `quality_passed`；Git 合并成功后调用 `event <任务 ID> merge_success --write`，合并失败调用 `event <任务 ID> merge_failure --reason "<冲突摘要>" --write`。两个合并事件只接受已持久化的 `quality_passed` 阶段。失败次数由脚本持久化到 `attempts` 字段，禁止从命令行重置。每波收口后传播下游阻塞：

   ```bash
   python <本 skill 目录>/scripts/workflow_control.py <tasks.md 路径> block --write
   ```
4. **合并**：波内过质量门的 task，其 worktree / 分支**依次**合并回主分支（`git merge --no-ff <task-branch>`），成功即标 `完成`、清理 worktree（`git worktree remove`）；冲突 → 标 `需人工`（记冲突文件）、**worktree 保留待人工**，跳过、继续合并其余。
   - **上游未合并 → 下游阻塞**：某 task 标 `需人工` 后，**依赖它的后波 task 一并标 `阻塞`**（记「上游 Task N 未合并」）、跳过 dispatch——否则后波会 dispatch 在缺该产物的 HEAD 上，破坏「先建后迁后删可编译」。上游经人工解决并合并后方可解阻。
5. **不停等用户**，进入下一波，直到所有波处理完。

> **现状类信息**（模块 / 接口 / 数据流怎么变）不沉淀——那是代码的职责。若本波某 task 引入值得沉淀的 intent，趁热预留「intent 沉淀」任务，回 SKILL 步骤 6 统一收口。

## 恢复中断

`tasks.md` 是进度真相源，续跑四步：

1. **收集外部事实**：运行 `git branch --merged <主分支>` 和 `git worktree list`，将确认已合并的任务 ID 作为输入；控制流内核不自行猜测 Git 状态。
2. **生成恢复计划**：

   ```bash
   python <本 skill 目录>/scripts/workflow_control.py <tasks.md 路径> recover --merged <任务 ID...>
   ```

   `skip` 不重跑；`complete` 补标完成；`inspect` 核对产物和质量门；`unblock` 解阻；`dispatch` 可进入新一波；`wait` 保持等待。
3. **执行并写回**：按计划处理残留 worktree 和质量门，使用合法 `event` 写回；已合并的「进行中」任务调用 `event <任务 ID> merge_success --write`。解阻任务在上游全部完成后调用 `event <任务 ID> unblock --write`，再重新进入批准的执行路径；不允许绕过状态机直接改状态。`需人工` task 的 worktree 保留供排查。

4. **重新计算**：再次运行 `waves` 和 `dispatchable`，逐波续跑，直至全部 task 为 `完成` / `需人工` / `阻塞`。

完成后**必须回到 SKILL 步骤 6**做交付前沉淀检查、给逐条判定结论再宣布交付——**恢复路径不豁免步骤 6**。

## 其他 CLI 工具（如 Codex）的上下文控制

无内置 Workflow 机制时，依赖**批次隔离 + 状态文件持久化**控制上下文：

1. **`tasks.md` 作为唯一真相源**：每个 CLI session 启动前读 `tasks.md`，结束后把状态（`完成` / `需人工` / `阻塞`）写回，不依赖会话内存。
2. **每次只跑一个波次**：取同一 wave 的独立任务启动新 session，跑完即退出，避免单 session 上下文累积。
3. **只返回摘要**：session prompt 明确要求只输出 `{ taskId, status, summary, issues }`，代码变更落到文件，不在会话内展开完整 diff / 日志。
4. **批次间压缩**：每波结束、主会话读取结果后执行 `/compact`，再续下一波。
5. **Codex 进阶**：`codex mcp-server` 暴露为 MCP 工具，由 OpenAI Agents SDK 外部编排，可实现类似 Workflow 的 session 隔离（参考 [OpenAI Cookbook](https://developers.openai.com/cookbook/examples/codex/codex_mcp_agents_sdk/building_consistent_workflows_codex_cli_agents_sdk)）。
