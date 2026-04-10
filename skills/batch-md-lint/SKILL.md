---
name: batch-md-lint
description: |
  批量检查多个 Markdown 文件的排版规范。接收多个文件路径或通配符，对每个文件并行调用 md-lint-worker 进行检查和修复，最后汇总输出结果。
  通过 subagent 并行处理多个文件，每个文件独立调用 md-lint 的单文件流程。
---

当此 skill 生效时，回答第一行固定写：Using skill: batch-md-lint

## 处理流程

### 步骤 1：确定文件列表

- 如果用户给了通配符，用 Glob 工具展开为具体文件路径列表
- 如果用户给了多个文件名，逐个确认路径存在
- 如果匹配到 0 个文件，告知用户没有匹配到文件，请检查路径
- 如果解析出的文件数超过 20 个，先警告用户并等待确认后再继续

### 步骤 2：并行分发

在**同一条消息**中，为每个文件发起一个 Agent 工具调用，实现真正的并行执行：

- 使用 `subagent_type: "md-lint-worker"`（已配置 `md-lint` 技能、所需工具和 `bypassPermissions` 权限）
- 使用 `run_in_background: true` 让 agent 在后台运行，不阻塞主对话，完成后自动通知
- prompt 中必须写明文件的**绝对路径**（subagent 是独立上下文，看不到主对话）
- 同时并行不超过 8 个文件，超过时分批处理
- 如果某个文件不存在，跳过并在汇总中报告

每个 Agent 的 prompt 模板如下：

```
请对文件 {绝对路径} 执行 Markdown 排版检查与修复。
```

示例（处理 3 个文件时，在一条消息中同时发起 3 个后台 Agent 调用）：

```
Agent({
  description: "md-lint: file1.md",
  subagent_type: "md-lint-worker",
  run_in_background: true,
  prompt: "请对文件 E:/docs/file1.md 执行 Markdown 排版检查与修复。"
})
Agent({
  description: "md-lint: file2.md",
  subagent_type: "md-lint-worker",
  run_in_background: true,
  prompt: "请对文件 E:/docs/file2.md 执行 Markdown 排版检查与修复。"
})
Agent({
  description: "md-lint: file3.md",
  subagent_type: "md-lint-worker",
  run_in_background: true,
  prompt: "请对文件 E:/docs/file3.md 执行 Markdown 排版检查与修复。"
})
```

### 步骤 3：汇总报告

所有 agent 返回后，汇总每个文件的处理结果：

## Markdown 排版检查报告

- **检查文件数**：N
- **需修复文件数**：N
- **已自动修复**：N

### 文件详情

| 文件 | 状态 | 问题数 | 修复项 |
|------|------|--------|--------|
| file1.md | 通过 | 0 | -- |
| file2.md | 已修复 | 5 | 中英文空格 x3, 全角标点 x2 |

### 未能自动修复的问题（如有）

列出需要人工介入的问题。
