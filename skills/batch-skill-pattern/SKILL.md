---
name: batch-skill-pattern
description: |
  批量技能的三层架构设计模式参考。当需要为一个单文件技能创建批量执行版本时，使用此模式。
  提供 skill → agent → skill 的分层架构模板，确保并发安全和权限正确。
disable-model-invocation: true
---

# 批量技能设计模式

当一个技能需要支持批量（多文件）执行时，采用以下三层架构：

## 架构总览

```
batch-xxx（skill）──调度层
  └─ xxx-worker（agent）──配置层
       └─ xxx（skill）──执行层
```

| 层级 | 类型 | 职责 |
|------|------|------|
| **调度层** `batch-xxx`（skill） | Skill | 文件列表展开、并行分发 Agent、汇总报告 |
| **配置层** `xxx-worker`（agent） | Agent | 声明 `permissionMode`、`tools`、`skills`、`model`，调用执行层技能 |
| **执行层** `xxx`（skill） | Skill | 单文件的实际处理逻辑 |

## 为什么需要三层

- **调度层和执行层分离**：单文件技能可独立使用，批量技能只负责编排，不重复业务逻辑
- **配置层（agent）不可省略**：后台 agent 的 `permissionMode` 必须写在 agent 定义文件中才能生效（调用时通过 `mode` 参数传入无效）；同时 agent 需要通过 `skills` 字段声明依赖的技能

## 模板

### 1. 执行层：`xxx/SKILL.md`

已有的单文件技能，无需修改。确保：
- 只处理单个文件
- 多文件时引导用户使用 `batch-xxx`

### 2. 配置层：`agents/xxx-worker.md`

```yaml
---
name: xxx-worker
description: 对单个文件执行 xxx 处理，供 batch-xxx 并行调度使用。
tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
  - Skill
  - WebFetch
skills:
  - xxx
model: sonnet
permissionMode: bypassPermissions
---

收到文件路径后，使用 Skill 工具调用 `xxx` 技能对该文件执行处理。

处理完成后，返回简洁的结果摘要。
```

关键字段说明：
- `tools`：列出执行层技能所需的全部工具
- `skills`：声明依赖的技能名称
- `permissionMode: bypassPermissions`：**必须**写在这里，不能依赖调用时传入
- `model: sonnet`：worker 用更快的模型即可

### 3. 调度层：`batch-xxx/SKILL.md`

```yaml
---
name: batch-xxx
description: 批量执行 xxx 处理。通过 subagent 并行处理多个文件。
---
```

核心流程：

1. **确定文件列表**：Glob 展开通配符，或逐个确认路径
2. **并行分发**：在同一条消息中发起多个 Agent 调用
   - `subagent_type: "xxx-worker"`
   - `run_in_background: true`
   - prompt 中写明文件**绝对路径**
   - 同时并行不超过 8 个文件，超过时分批
3. **汇总报告**：所有 agent 返回后，用表格汇总结果

Agent 调用示例：

```
Agent({
  description: "xxx: file1.md",
  subagent_type: "xxx-worker",
  run_in_background: true,
  prompt: "请对文件 /absolute/path/to/file1.md 执行 xxx 处理。"
})
```

## 并发安全检查清单

为执行层技能添加并发安全保障：
- [ ] 不使用固定名称的临时文件（用 `mktemp` 或 PID 后缀）
- [ ] 不依赖共享的全局状态
- [ ] 每个文件的产出路径互不冲突（如用文件名前缀区分）
- [ ] 在技能文件顶部添加并发安全提醒注释

## 实际案例

参考 `batch-md-fmt` → `md-fmt-worker` → `md-fmt` 的实现。
