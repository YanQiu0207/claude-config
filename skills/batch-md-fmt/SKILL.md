---
name: batch-md-fmt
description: |
  批量对多个 Markdown 文件进行一站式标准化：先排版规范化，再网络图片本地化。当用户提供多个文件路径或使用通配符（如 `*.md`、`**/*.md`）进行 markdown 标准化时触发。
  通过 subagent 并行处理多个文件，每个文件独立调用 md-fmt 的单文件流程。
---

当此 skill 生效时，回答第一行固定写：Using skill: batch-md-fmt

## 处理流程

### 步骤 1：确定文件列表

- 如果用户给了通配符，用 Glob 工具展开为具体文件路径列表
- 如果用户给了多个文件名，逐个确认路径存在
- 如果匹配到 0 个文件，告知用户没有匹配到文件，请检查路径

### 步骤 2：并行分发

在**同一条消息**中，为每个文件发起一个 Agent 工具调用，实现真正的并行执行：

- 使用 `subagent_type: "md-fmt-worker"`（已配置 `md-fmt` 技能、所需工具和 `bypassPermissions` 权限）
- 使用 `run_in_background: true` 让 agent 在后台运行，不阻塞主对话，完成后自动通知
- prompt 中必须写明文件的**绝对路径**（subagent 是独立上下文，看不到主对话）
- 同时并行不超过 8 个文件，超过时分批处理

每个 Agent 的 prompt 模板如下：

```
请对文件 {绝对路径} 执行 Markdown 标准化处理。
```

示例（处理 3 个文件时，在一条消息中同时发起 3 个后台 Agent 调用）：

```
Agent({
  description: "md-fmt: file1.md",
  subagent_type: "md-fmt-worker",
  run_in_background: true,
  prompt: "请对文件 E:/work/blog/ai/file1.md 执行 Markdown 标准化处理。"
})
Agent({
  description: "md-fmt: file2.md",
  subagent_type: "md-fmt-worker",
  run_in_background: true,
  prompt: "请对文件 E:/work/blog/ai/file2.md 执行 Markdown 标准化处理。"
})
Agent({
  description: "md-fmt: file3.md",
  subagent_type: "md-fmt-worker",
  run_in_background: true,
  prompt: "请对文件 E:/work/blog/ai/file3.md 执行 Markdown 标准化处理。"
})
```

### 步骤 3：汇总报告

所有 agent 返回后，汇总每个文件的处理结果，格式：

| 文件 | 排版 | 图片 | 备注 |
|------|------|------|------|
| file1.md | 已修改 | 3 成功 / 0 失败 | |
| file2.md | 无需修改 | 无网络图片 | |
| file3.md | 已修改 | 2 成功 / 1 失败 | 失败: http://... |
