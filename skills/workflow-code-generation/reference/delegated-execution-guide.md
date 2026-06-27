# 下放 agent 执行指南

> 本手册承接 `workflow-code-generation` SKILL 步骤 5：tasks.md 批准后的下放执行细则。单 task = 1 波 1 agent，多 task 无依赖 = 并行分波。

## 编排模型：先判定 CLI 嵌套能力

`workflow-code-review` 会按 task 风险派轻量 / 标准 / 严格 reviewer 集。**子 agent 能否再派子 agent**（嵌套 dispatch）决定 review / verify 跑在哪层。

- **实测**：派一个子 agent，让它再派一个孙 agent 回一句话；成功即支持。
- Claude Code **支持**嵌套（版本号与来源见框架根 `docs/03-parallel-execution-mode.md`，可能随 CLI 更新而变）；**最终以实测为准**。
- ⚠️ **嵌套深度上限 5 层**（固定、不可配置；第 5 层子 agent 不再获得 `Agent` 工具）。模式 A 链深 3 层（主 agent → owner → reviewer），勿设计更深的派生链。

| 模式 | 适用 | owner / implementer 职责 | 质量门跑在哪 |
| --- | --- | --- | --- |
| **A（默认）** | 支持嵌套（Claude Code） | owner 自闭环：实现 → 调用 `workflow-test-generation` → 测试通过 → 自跑 review → 有限轮次自修复 → 返回结论 | owner 子 agent 内 |
| **B（兜底）** | 不支持嵌套（其他 CLI） | implementer 只实现 + 写 / 跑测试 | 主 agent 对每个产物跑 |

两模式只差「质量门跑在哪层」，其余流程一致。

## Claude Code 专属：Workflow 工具编排（推荐，规避主会话上下文膨胀）

模式 A 用 `Agent` 工具派 owner agent，子 agent 的全部输出追加到主会话上下文，长程任务容易撑爆。**Claude Code 改用 `Workflow` 工具**——脚本后台运行，完成后只返回最终报告，主上下文不膨胀。

**主会话操作**：读取 `tasks.md`，按 `depends_on` 归组成波次数组，调用 `Workflow` 工具并将波次作为 `args` 传入：

```javascript
export const meta = {
  name: 'code-gen-waves',
  description: '按波次并行执行代码生成任务',
  phases: [{ title: '执行' }, { title: '汇总' }],
}

const RESULT_SCHEMA = {
  type: 'object',
  required: ['taskId', 'status', 'summary', 'verify_command', 'verify_report_path', 'spec_drift'],
  properties: {
    taskId:             { type: 'string' },
    status:             { type: 'string', enum: ['完成', '需人工', '阻塞'] },
    summary:            { type: 'string' },
    verify_command:     { type: 'string' },
    verify_report_path: { type: 'string' },
    spec_drift:         { type: 'string' },
    issues:             { type: 'array', items: { type: 'string' } },
  },
}

// args.base_sha: Phase 0 记录的 git rev-parse HEAD
// args.baseline_path: 有 verify.config.json 时为 <repo-root>/.verify/baseline.json；无 config 时为空
// args.waves: [[{ id, title, context_files, verification, artifacts, review_profile }, ...], ...]
// 波次顺序执行（满足 depends_on 语义），波内任务并行
const allResults = []
for (const wave of args.waves) {
  phase('执行')
  const waveResults = await parallel(wave.map(task => () =>
    agent(
      `你是 ${task.id} 的 owner agent。\n` +
      `任务：${task.title}\nReview 档位：${task.review_profile}\nContext：${task.context_files}\n验证：${task.verification}\n产物：${task.artifacts}\n\n` +
      `完成后依次执行：\n` +
      `1. 确认所有子任务已完成；测试子任务须已调用 workflow-test-generation 生成并运行通过\n` +
      `2. 按 task.review_profile 加载 workflow-code-review 并修复\n` +
      `3. 加载 workflow-verification 跑机器验证；有 config 必须传 --baseline ${args.baseline_path} --diff-base ${args.base_sha}，无 config 必须传 --diff-base ${args.base_sha}；FAIL 则修复重跑\n` +
      `4. 返回 verify_command、verify_report_path、spec_drift 结论；不输出完整 diff`,
      { label: task.id, phase: '执行', schema: RESULT_SCHEMA, isolation: 'worktree' }
    )
  ))
  allResults.push(...waveResults.filter(Boolean))
}

phase('汇总')
return { results: allResults }
```

Workflow 完成后，主会话拿到 `results` 数组，逐条更新 `tasks.md` 状态字段，继续后续波次或进入 SKILL 步骤 6。

> **与 Phase 1 的关系**：本方案替代 Phase 1 中「主会话用 `Agent` 工具 dispatch」的部分；失败隔离、合并、`tasks.md` 状态写回的逻辑由 owner agent 在脚本内执行，规则与 Phase 1 一致。

## Phase 0：准备

1. **加载编码规范**（步骤 4 已做）。
2. **记录 diff 基准**：动代码前记录 `base_sha=$(git rev-parse HEAD)`；后续所有 worktree 与最终验证都显式传 `--diff-base <base_sha>`，避免提交 / 合并后工作区 clean 导致 spec drift 误判无改动。
3. **采机器验证基线**：若项目根有 `verify.config.json`，在动代码前 `python <skill-dir>/scripts/verify.py --save-baseline <repo-root>/.verify/baseline.json`，并把该绝对路径作为 `baseline_path` 传入 Workflow；无 config 时 `baseline_path` 为空。
4. **校验依赖**：跑 `python scripts/lint_task_deps.py <tasks.md 路径>` 检查 dangling 依赖、循环依赖、以及「改同一文件却无依赖关系」的并行冲突。有 ERROR 必须先修；有 WARN（潜在并行冲突）逐条确认是补 `depends_on` 还是确属可并行。
5. **构建依赖波（wave）并传入 Workflow**：完整读取 `tasks.md`，按 `depends_on` 做拓扑分层，产出 `waves` 数组：
   ```
   wave 1: [无前置依赖的 task]
   wave 2: [依赖仅来自 wave 1 的 task]
   wave N: [依赖均已在前序波完成的 task]
   ```
   将 `waves` 作为 `args.waves` 传入 Workflow 工具（见下方脚本示例）。缺 `depends_on` 无法判断 → 保守串行（每波 1 个 task）或回问，**禁止对未知依赖全并行**。单 task 即单波。

## Phase 1：逐波执行（波内并行，波间串行）

> 🗂 **`tasks.md` 是进度真相源**：每个 task 的 `状态:` 字段实时写回（`未开始` / `进行中` / `完成` / `需人工` / `阻塞`）——dispatch 标 `进行中`，合并成功标 `完成`，失败 / 冲突标 `需人工`（附原因 + 失败输出），上游未合并的下游标 `阻塞`。每步完成即更新，中断后靠它续跑。

对每个 wave：

1. **dispatch**：波内每个 task 派一个子 agent（A 为 owner、B 为 implementer），各自在隔离 git worktree（基于当前分支 HEAD）工作，受并发上限约束、超出排队。多个子 agent **在同一条消息里并行派发**。
   - worktree：用 Agent 工具的 `isolation: "worktree"`，或 `git worktree add -b <task-branch> <path> HEAD`。
   - prompt 公共部分：task 描述 + `context_files`（直接改文件 + 上游 + 下游）+ `verification` + `artifacts` + `spec` / `tasks` 摘要 + 编码规范要点 + worktree 路径 + 「只在此 worktree 内改、改完提交」。
   - 职责见上方编排模型表（A 自闭环 / B 只实现 + 测试）。**测试与实现同批**：接口层与核心逻辑必须有覆盖关键路径、能跑通的测试，不允许先实现后补。
2. **质量门**（review + 机器验证，两者都过才算通过）：
   - 模式 A：owner 已跑完 review 与 `workflow-verification`，主 agent 只**收集**结论。
   - 模式 B：主 agent 对每个产物（在其 worktree 内）扮演 `workflow-code-review` 的 Judge 按 `review_profile` 裁决，再跑 `workflow-verification` 机器验证。
3. **失败隔离**：测试 / review / 机器验证 任一不过 → 有限轮次（≤ 2）自修复重跑（A 在 owner 内、B 由主 agent 派 fixer 在同一 worktree 修）；仍不过、或子 agent 报范围 / 依赖问题无法在本 task 内解决 → 标 `需人工` 附原因 + 失败输出（review finding / 错误摘要）；**子 agent 崩溃 / 超时 / 无产物返回** → 标 `需人工` 注「agent 未返回，需重 dispatch」。标 `需人工` 的 task **其 worktree 保留**供排查、不清理。以上**均不阻塞同波其他 task、不停整个流程**。
4. **合并**：波内过质量门的 task，其 worktree / 分支**依次**合并回主分支（`git merge --no-ff <task-branch>`），成功即标 `完成`、清理 worktree（`git worktree remove`）；冲突 → 标 `需人工`（记冲突文件）、**worktree 保留待人工**，跳过、继续合并其余。
   - **上游未合并 → 下游阻塞**：某 task 标 `需人工` 后，**依赖它的后波 task 一并标 `阻塞`**（记「上游 Task N 未合并」）、跳过 dispatch——否则后波会 dispatch 在缺该产物的 HEAD 上，破坏「先建后迁后删可编译」。上游经人工解决并合并后方可解阻。
5. **不停等用户**，进入下一波，直到所有波处理完。

> **现状类信息**（模块 / 接口 / 数据流怎么变）不沉淀——那是代码的职责。若本波某 task 引入值得沉淀的 intent，趁热预留「intent 沉淀」任务，回 SKILL 步骤 6 统一收口。

## 恢复中断

`tasks.md` 是进度真相源，续跑三步：

1. **定位**：找 `进行中` / `未开始` / `阻塞` 的 task；`进行中` 优先（上次很可能中断在它身上）；`阻塞` 先看上游是否已合并，已合并则解阻。
2. **处理 worktree 残留**：`git worktree list`，按分支名 `<task-branch>` 回连 `tasks.md` 的 task——
   - 对应 `进行中` task：**先 `git branch --merged <主分支>` 核对是否已并入主分支**（防中断在「已合并未标完成」窗口）；已合并 → 标 `完成`、清理，不重跑；未合并 → 核对产物是否过质量门，过了就合并标 `完成`，没过就重跑质量门或重新 dispatch。
   - 对应 `需人工` task：**保留不动**（供人工排查）。
   - 分支名回连不到任何 task 的废弃 worktree：清理掉。
3. **重载规范 → 重建依赖波 → 继续下放执行**，直至全部 task 为 `完成` / `需人工` / `阻塞`（`阻塞` 项须待其上游经人工解决后下次续跑再处理，本身即可接受终态）。

完成后**必须回到 SKILL 步骤 6** 做交付前沉淀检查、给逐条判定结论再宣布交付——**恢复路径不豁免步骤 6**。

## 其他 CLI 工具（如 Codex）的上下文控制

无内置 Workflow 机制时，依赖**批次隔离 + 状态文件持久化**控制上下文：

1. **`tasks.md` 作为唯一真相源**：每个 CLI session 启动前读 `tasks.md`，结束后把状态（`完成` / `需人工` / `阻塞`）写回，不依赖会话内存。
2. **每次只跑一个波次**：取同一 wave 的独立任务启动新 session，跑完即退出，避免单 session 上下文累积。
3. **只返回摘要**：session prompt 明确要求只输出 `{ taskId, status, summary, issues }`，代码变更落到文件，不在会话内展开完整 diff / 日志。
4. **批次间压缩**：每波结束、主会话读取结果后执行 `/compact`，再续下一波。
5. **Codex 进阶**：`codex mcp-server` 暴露为 MCP 工具，由 OpenAI Agents SDK 外部编排，可实现类似 Workflow 的 session 隔离（参考 [OpenAI Cookbook](https://developers.openai.com/cookbook/examples/codex/codex_mcp_agents_sdk/building_consistent_workflows_codex_cli_agents_sdk)）。
