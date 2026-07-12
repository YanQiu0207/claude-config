---
name: workflow-code-review
description: 代码评审。按风险档位协调 reviewer subagent 进行并行多维度审查：小需求可轻量审，高风险才全量 5 维 + critic。可由用户直接触发，也可由主 agent 加载后作为 Judge 执行。
---

> 输出一行：`Using workflow-code-review`

# Multi-Agent Code Review

你是 **Judge**——编排流程、去重分诊、最终裁决、输出报告。你不是 reviewer，不产出 finding。

当 `review_profile: strict` 时，Judge 必须与本次改动的 owner / implementer 不是同一执行主体。owner / implementer 不得调用本 skill 完成最终裁决，只能提交产物、接收 keep finding 并修复；若当前调用者参与过实现，必须将 review 上提给主 agent 或另一个独立 Judge Agent。

## Review 档位

| 档位 | 适用 | 调用 reviewer |
| --- | --- | --- |
| `lightweight` | 小需求 / 低风险：局部改动，或不改变接口、契约、控制流与模块交互的跨文件机械重复改动；不碰数据 / 权限 / 并发 / 安全 / 性能关键路径 | `comprehensive-reviewer`（一趟覆盖工程规范、需求符合度、正确性与健壮性） |
| `standard` | 默认档：普通功能、Bug 修复，或涉及多个模块之间的行为、契约、交互变化但风险可控 | `standards-reviewer`、`spec-compliance-reviewer`、`robustness-reviewer` |
| `strict` | 高风险：生产关键路径、安全 / 权限 / 数据迁移 / 并发 / 分布式 / 性能敏感 / 公共 API / 大范围重构 | 全量 5 reviewer；有 finding 时调用 `review-critic` |

调用方可显式传入 `review_profile: lightweight|standard|strict`。未传入时按范围和风险自行判定；无法判断时用 `standard`，命中高风险任一条件时用 `strict`。

## Subagent 清单

| 角色 | subagent_name | 调用方式 |
|------|---------------|----------|
| 轻量综合审查 | `comprehensive-reviewer` | 仅 `lightweight` 调用（一趟覆盖工程规范、需求符合度、正确性与健壮性） |
| 性能审查 | `performance-reviewer` | `strict` 调用；性能敏感任务在 `standard` 中也可加入 |
| 健壮性审查 | `robustness-reviewer` | `standard` / `strict` 调用 |
| 工程规范审查 | `standards-reviewer` | `standard` / `strict` 调用 |
| 契约与信任链审查 | `magical-prompt-reviewer` | `strict` 调用；涉及 prompt / 外部工具 / 权限边界时必须加入 |
| 需求/设计符合度审查 | `spec-compliance-reviewer` | `standard` / `strict` 调用 |
| 对抗性验证 | `review-critic` | `strict` 有 finding 时调用；`standard` 出现 P0 / P1 finding 时调用 |

## 复审模式（re-review）

修复-复审循环的第二轮及以后**必须**用本模式，不得重跑全量首轮。调用方传入 `rereview: true`、上一轮报告（裁决明细 + 正式问题）和修复 diff。

与首轮的差异：

- **核验范围只有两件事**：上一轮 keep 的每条 finding 是否已修复；修复 diff 本身是否引入新问题。**禁止对修复 diff 之外的代码提出新 finding**——全量扫描是首轮的责任，不靠复审轮补漏。
- **派发收窄**：只派上一轮 keep finding 所属维度的 reviewer（每维度一个）；`review-critic` 不参与复审，除非复审轮新增 P0 / P1 finding。
- **无上一轮 keep finding 的修复**（机器验证 / 前端验证等非 review finding 触发的代码修复）：只执行第二件事——核验修复 diff 是否引入新问题；reviewer 按当前 `review_profile` 的组合派发，审查范围仍限修复 diff。
- **输出增量报告**：沿用第 7 步固定模板，轮次写「复审第 N 轮」（N = 上一轮轮次 + 1，首审记第 0 轮；无上一轮报告的验证类修复复审从第 1 轮起）。裁决明细中每条原 finding 标「已修复 / 未修复 / 部分修复」+ 依据；正式问题区只列未修复 / 部分修复的原 finding 与修复引入的新 finding（沿用 `F-{seq}` 续号），新 finding 标题加「（新增）」，如 `#### P1-2（新增）: ...`；总体结论仍为 PASS / NEEDS_CHANGES。

### 循环语义（调用方必须遵守）

- 仅总体结论为 `NEEDS_CHANGES`（存在 keep 的 P0 / P1）触发「修复 → 复审」循环；**P2 与 follow-up note 不触发循环**，原样记入报告交用户决定。
- 修复-复审最多 2 轮；第 2 轮复审仍 `NEEDS_CHANGES` → 调用方标「需人工」终止，禁止继续循环。

## 工作流

### 1. 解析 review 范围

根据用户输入确定审查文件、diff 来源和 `review_profile`。若范围不清，先澄清再继续。

> 调用方传入 `rereview: true` → 按上方「复审模式」执行（收窄核验范围与派发），不走全量首轮流程；Step 4-7 的去重、裁决与报告规则仍适用于复审产物。

- 指定文件/spec/task → 直接使用
- 给出 git diff/commit → 解析变更文件
- 无具体范围 → `git diff --cached` 或 `git diff HEAD`

### 2. 构建共享上下文

- 在 `docs/design-docs/` 下搜索相关 `spec.md` 和 `tasks.md`
- 确定审查文件、上下文文件（caller/callee/接口定义）
- 根据文件类型和目录确定适用 skill；若目录结构或 spec.md 显示 DDD 分层（adapter / domain / application / infrastructure），将 `bp-cola-ddd` 加入 `{skill_list}` 传入 `standards-reviewer` 和 `spec-compliance-reviewer`；若改动涉及架构边界 / 模块划分或组件接口 / 数据模型设计，相应将 `bp-architecture-design` / `bp-component-design` 加入 `{skill_list}`
- 提炼与本次 review 相关的 spec/task 摘要

### 3. 并行分派 reviewer

按 `review_profile` **并行**调用对应 reviewer subagent。**必须等待本档位所有 reviewer subagent 返回后才能进入 Step 4**——禁止主 agent 自己产出 finding。

**跳过 / 追加列表**：调用方可在请求中通过 `skip_reviewers: [name1, name2]` 跳过某些 reviewer，或通过 `extra_reviewers: [name1]` 给当前档位追加 reviewer。未指定时按 `review_profile` 调用。

每个 reviewer 的 prompt 按以下模板构建：

```
审查以下代码变更，在你的维度内产出候选 finding。

[Review Scope]
- 审查文件：{files_under_review}
- 上下文文件：{context_files 或 None}
- Spec：{spec_path 或 N/A}
- Tasks：{tasks_path 或 N/A}
- 当前 Task：{task_id 或 N/A}
- 适用 skill：{skill_list}
- 变更摘要：{scope_summary}

[Severity]
- P0：应阻止合入（功能错误、数据错误、崩溃、严重并发错误、与 spec 关键偏离）
- P1：应该修复但不一定阻塞（特定条件触发、影响可控但风险明确）
- P2：改进建议（不影响正确性/稳定性/性能基线）

只报你的维度内的问题。其他维度的线索可以用一行 handoff note 提示。
```

### 4. 去重归类 & 输出 Reviewer 意见汇总

收齐结果后：
- 合并同根因 / 同位置 / 同调用链的 finding，保留最高 severity
- 归类整理所有 finding，为每条分配全局唯一编号 `F-{seq}`

**零 finding 快速路径**：若所有 reviewer 均无正式 finding，直接跳到第 7 步输出 PASS 报告。

完成去重后，**立即向用户输出 Reviewer 意见汇总**（让用户看到各维度的原始审查视角）：

```markdown
---

## 📋 Reviewer 意见汇总

> 只列本档位实际调用的 reviewer 分节。`lightweight` 档仅 `comprehensive-reviewer` 一节。

### 轻量综合审查 (comprehensive-reviewer，仅 lightweight 档)

- **F-1** [P1 · 需求符合度]
  - **位置**: `file:line`
  - **问题**: [一句话问题摘要]
  - **证据**: [支撑该问题的关键代码片段/数据/逻辑推理]
- 💡 **Handoff notes**: [发现的超出轻量档的高风险线索 + 是否建议升档，无则省略此行]

### 性能审查 (performance-reviewer)

- **F-1** [P1]
  - **位置**: `file:line`
  - **问题**: [一句话问题摘要]
  - **证据**: [支撑该问题的关键代码片段/数据/逻辑推理]
- **F-2** [P2]
  - **位置**: `file:line`
  - **问题**: [一句话问题摘要]
  - **证据**: [支撑该问题的关键代码片段/数据/逻辑推理]
- 💡 **Handoff notes**: [该 reviewer 发现但属于其他维度的线索，无则省略此行]

### 健壮性审查 (robustness-reviewer)

- **F-3** [P0]
  - **位置**: `file:line`
  - **问题**: [一句话问题摘要]
  - **证据**: [支撑该问题的关键代码片段/数据/逻辑推理]
- 💡 **Handoff notes**: ...

### 工程规范审查 (standards-reviewer)

（同上格式，无 finding 则显示"✅ 无发现"）

### 契约与信任链审查 (magical-prompt-reviewer，如本档位调用)

（同上格式）

### 需求/设计符合度审查 (spec-compliance-reviewer)

（同上格式）

---
```

### 5. 按档位调用 critic & 输出 Critic 意见

仅在以下情况调用 `review-critic` subagent：`strict` 档有 finding，或 `standard` 档出现 P0 / P1 finding。`lightweight` 档默认不调用 critic，除非 Judge 判断 finding 影响面超出小需求边界，应升级为 `standard` 或 `strict` 后重审。需要调用 critic 时，**必须等待 critic subagent 返回后才能进入 Step 6**——禁止主 agent 自己做对抗性验证：

```
[Issue 列表]
（逐条列出 F-{seq}、claim、evidence、location、severity、assumptions）

[Review 上下文]
- 相关文件：{files}
- Spec：{spec_path 或 N/A}
- Tasks：{tasks_path 或 N/A}
- 当前 Task：{task_id 或 N/A}
```

收到 critic 结果后，**立即向用户输出 Critic 意见**：

```markdown
---

## 🔍 Critic 对抗性验证

- **F-1** ✅ 成立
  - **问题**: [reviewer 发现的问题简述]
  - **理由**: [为什么同意 reviewer，补充验证证据]
- **F-2** ❌ 驳回
  - **问题**: [reviewer 发现的问题简述]
  - **理由**: [反证摘要：为什么不成立]
- **F-3** ⚠️ 降级
  - **问题**: [reviewer 发现的问题简述]
  - **理由**: [部分成立但严重度应降低的理由]

---
```

> Critic 结论类型：✅ 成立（同意 reviewer）、❌ 驳回（提供反证）、⚠️ 降级（部分成立但建议降低 severity）。

### 6. 最终裁决

**主 agent 必须亲自调研后裁决**——不能简单采信 reviewer 或 critic 的结论。对每条 issue：

1. **独立调研**：阅读相关代码上下文（调用方、被调用方、数据流）、spec 设计意图、相关注释和 git history，形成自己对该问题的理解
2. **交叉验证**：将 reviewer 提出的证据、critic 的反证与自己调研的结果三方对比
3. **基于证据裁决**：
   - **keep**：问题成立，按 P0/P1/P2 分类进入报告正式问题区
   - **drop**：经调研确认 critic 反证成立或证据不足，丢弃
   - **follow-up note**：不够正式 finding 但值得提醒，进入报告 Follow-up Notes 区（不分级）

> ⚠️ 裁决理由必须引用具体的代码位置、spec 条目或上下文事实，禁止使用"证据充分""证据不足"等空泛表述。

通过门槛：
- 存在 keep 的 P0/P1 → `NEEDS_CHANGES`
- 无 keep 的 P0/P1 → `PASS`
- P2 不阻塞通过

### 7. 输出最终报告

按以下模板输出（整个系统唯一固定格式）。该模板同时是遥测质量账的解析接口（见 [11-session-telemetry.md](../../docs/11-session-telemetry.md)），「轮次」字段与复审报告的「（新增）」标记是指标数据源，不得省略：

```markdown
# Code Review 报告

## 审查范围
- **Spec**: [路径 或 N/A]
- **Tasks**: [路径 或 N/A]
- **当前 Task**: [ID/名称 或 N/A]
- **轮次**: 首审 / 复审第 N 轮
- **审查文件**: [文件列表]

## 总体结论: PASS / NEEDS_CHANGES

## 裁决明细

> 对每条候选 finding 的最终处置和理由，完整展示审查过程的透明度。

- **F-1** [reviewer名 · 原始优先级] → ✅/❌/⚠️ Critic 结论 → **最终处置 (keep/drop/降级/follow-up)**
  - 裁决依据：[简述经调研后认定成立或不成立的理由]
- **F-2** [reviewer名 · 原始优先级] → ✅/❌/⚠️ Critic 结论 → **最终处置**
  - 裁决依据：[简述理由]
- ...

## 正式问题

### P0（必须修复）

#### P0-1: [问题标题]
- **维度**: [来源维度]
- **位置**: `file:line`
- **问题**: [描述]
- **证据**: [关键证据]
- **建议**: [修复方式]

### P1（应该修复）
...

### P2（建议改进）
...

## Follow-up Notes
- [少量不够进入正式 finding 但值得提醒的事项]
```
