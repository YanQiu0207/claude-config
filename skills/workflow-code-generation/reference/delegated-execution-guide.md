# 下放 agent 执行指南

> 本手册承接 `workflow-code-generation` SKILL 步骤 5：tasks.md 批准后的下放执行细则。单 task = 1 波 1 agent，多 task 无依赖 = 并行分波。

## 编排模型：先判定 CLI 嵌套能力

`workflow-code-review` 要派 reviewer 子 agent。**子 agent 能否再派子 agent**（嵌套 dispatch）决定 review / verify 跑在哪层。

- **实测**：派一个子 agent，让它再派一个孙 agent 回一句话；成功即支持。
- Claude Code **支持**嵌套（版本号与来源见框架根 `docs/03-parallel-execution-mode.md`，可能随 CLI 更新而变）；**最终以实测为准**。
- ⚠️ **嵌套深度上限 5 层**（固定、不可配置；第 5 层子 agent 不再获得 `Agent` 工具）。模式 A 链深 3 层（主 agent → owner → reviewer），勿设计更深的派生链。

| 模式 | 适用 | owner / implementer 职责 | 质量门跑在哪 |
| --- | --- | --- | --- |
| **A（默认）** | 支持嵌套（Claude Code） | owner 自闭环：实现 → 内嵌测试 → 自跑 review → 自跑 verify → 有限轮次自修复 → 返回结论 | owner 子 agent 内 |
| **B（兜底）** | 不支持嵌套（其他 CLI） | implementer 只实现 + 写 / 跑测试 | 主 agent 对每个产物跑 |

两模式只差「质量门跑在哪层」，其余流程一致。

## Phase 0：准备

1. **加载编码规范**（步骤 4 已做）。
2. **采基线（仅当根目录有 `verify.config.json`）**：加载 `workflow-verification`，`verify.py --save-baseline .verify/baseline.json`，并记下其**主仓库根绝对路径** `<repo-root>/.verify/baseline.json`——worktree 基于 HEAD 新建、看不到这个未提交（通常已 gitignore）的基线，Phase 1 必须用绝对路径引用。
   > ⚠️ `verify.config.json` 的命令以 shell 执行。自己的仓库直接跑；处理外部分支且 config 含未审查变更时，**先人工确认命令安全**再执行。无 config 则跳过。
3. **构建依赖波（wave）**：按各 task 的 `depends_on` 拓扑分层——同波内 task 互不依赖、可并行；后波依赖前波产物、等前波合并后再开始。缺 `depends_on` 无法判断 → 保守串行或回问，**禁止对未知依赖全并行**。单 task 即单波。

## Phase 1：逐波执行（波内并行，波间串行）

> 🗂 **`tasks.md` 是进度真相源**：每个 task 的 `状态:` 字段实时写回（`未开始` / `进行中` / `完成` / `需人工` / `阻塞`）——dispatch 标 `进行中`，合并成功标 `完成`，失败 / 冲突标 `需人工`（附原因 + 失败输出），上游未合并的下游标 `阻塞`。每步完成即更新，中断后靠它续跑。

对每个 wave：

1. **dispatch**：波内每个 task 派一个子 agent（A 为 owner、B 为 implementer），各自在隔离 git worktree（基于当前分支 HEAD）工作，受并发上限约束、超出排队。多个子 agent **在同一条消息里并行派发**。
   - worktree：用 Agent 工具的 `isolation: "worktree"`，或 `git worktree add -b <task-branch> <path> HEAD`。
   - prompt 公共部分：task 描述 + context（直接改文件 + 上游 + 下游）+ `spec` / `tasks` 摘要 + 编码规范要点 + worktree 路径 + 「只在此 worktree 内改、改完提交」。
   - 职责见上方编排模型表（A 自闭环 / B 只实现 + 测试）。**测试与实现同批**：接口层与核心逻辑必须有覆盖关键路径、能跑通的测试，不允许先实现后补。
2. **质量门**：
   - 模式 A：owner 已跑完，主 agent 只**收集**结论。
   - 模式 B：主 agent 对每个产物（在其 worktree 内）扮演 `workflow-code-review` 的 Judge 派 reviewer（`skip_reviewers: [magical-prompt-reviewer]`）裁决。
   - **verify（两模式一致，仅当有 config 或 Phase 0 已采基线）**，在产物所在 worktree 内：
     - 已采基线 → `verify.py --baseline <repo-root>/.verify/baseline.json`（**用绝对路径**；worktree 看不到相对路径基线，会静默跳过基线对比、清零「测试数不得减少」等防回退检查）。绝对路径不可达 → 按门禁故障（ERROR）处理，**不得**静默退回无基线路径。
     - 仅有 config → `verify.py`。
     - 退出码 0 过；1（新增违规）回修；2（门禁故障）停止交付、排查后重跑，不当作新增违规改代码。
3. **失败隔离**：测试 / review / verify 任一不过 → 有限轮次（≤ 2）自修复重跑（A 在 owner 内、B 由主 agent 派 fixer 在同一 worktree 修）；仍不过、或子 agent 报范围 / 依赖问题无法在本 task 内解决 → 标 `需人工` 附原因 + 失败输出（review finding / verify 报告 / 错误摘要）；**子 agent 崩溃 / 超时 / 无产物返回** → 标 `需人工` 注「agent 未返回，需重 dispatch」。标 `需人工` 的 task **其 worktree 保留**供排查、不清理。以上**均不阻塞同波其他 task、不停整个流程**。
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
