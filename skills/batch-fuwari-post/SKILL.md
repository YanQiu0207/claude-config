---
name: batch-fuwari-post
description: |
  批量将多个 Markdown 文件/目录迁移到 Fuwari 博客的 posts 目录，每篇以独立子目录组织（`posts/<slug>/index.md` + 同目录图片），并生成 frontmatter。
  当用户提供多个文件路径、一个或多个目录、或通配符（如 `*.md`、`**/*.md`）时触发。
  通过并行派发 `fuwari-post-worker` 后台 agent 加速处理。
argument-hint: "<文件/目录/通配符列表> [目标 posts 根目录]"
model: sonnet
---

当此 skill 生效时，回答第一行固定写：Using skill: batch-fuwari-post

## 输入

- **必填**：一个或多个路径，支持以下形式混合出现：
  - 单个文件路径：`a.md`
  - 多个文件路径：`a.md b.md c.md`
  - 单个目录：`E:/work/blog/分布式基础`（递归查找其下 `*.md`）
  - 多个目录：多个目录路径
  - 通配符：`**/*.md`、`分布式基础/**/*.md`
- **可选**：目标 posts 根目录（默认 `E:/github/yanqiu0207.github.io/src/content/posts`）

## 处理流程

### 步骤 1：展开文件列表

对用户给定的每个输入项：

1. **通配符** → 用 Glob 工具展开
2. **目录** → 用 Glob 递归查找 `<dir>/**/*.md`
3. **文件路径** → 用 Read 或 Bash 验证存在性

合并去重后得到最终 md 文件列表，统一转为**绝对路径**。

边界处理：

- 0 个文件：告知用户没有匹配到文件，请检查路径后终止
- 超过 20 个文件：先列出前 10 个 + 总数，请用户确认后继续
- 排除目标 posts 目录下已有的 `*.md`（避免误操作自己的产物）

### 步骤 2：记录起始时间

执行 `date +%s` 记录批量起始时间戳。

### 步骤 3：并行分发

**关键**：所有 Agent 调用必须在**同一条消息**中同时发出，否则会退化为串行执行。

对每个文件派发一个后台 agent：

```javascript
Agent({
  description: "fuwari-post: <文件名>",
  subagent_type: "fuwari-post-worker",
  run_in_background: true,
  prompt: "请使用 Skill 工具调用 fuwari-post 技能，将源文件 <源文件绝对路径> 迁移到目标 posts 根目录 <posts_root>。"
})
```

- 每批最多 **8 个** 并行 agent
- 超过 8 个时分批，等前一批 task-notification 全部返回后再派发下一批
- prompt 中必须写明：**源文件绝对路径** + **目标 posts 根目录绝对路径**（后台 agent 是独立上下文，看不到主对话）

### 步骤 4：汇总报告

所有 agent 返回后，执行 `date +%s` 记录结束时间，输出以下表格：

| 文件 | Slug | 图片（本地/下载/失败） | category | 耗时 | 备注 |
|------|------|----------------------|----------|------|------|
| logic-clock.md | logic-clock | 0 / 1 / 0 | 分布式基础 | 12s | |
| cap.md | cap | 0 / 2 / 1 | 分布式基础 | 18s | 失败: http://... |
| ... | ... | ... | ... | ... | ... |

末尾追加：

- **成功**：N 篇
- **失败**：M 篇（列出文件名）
- **批量总耗时**：X 秒（墙钟时间）

其中每个文件的单项耗时取自其 task-notification 的 `duration_ms`，转换为秒（保留整数）。

## 边界情况

- **某个文件处理失败**：在汇总表中标记失败原因，不中断其他文件
- **slug 冲突**（多个源文件生成相同 slug）：在派发前检测并提示用户，让用户决定是否重命名
- **目标 posts 根目录不存在**：先创建，再派发
- **用户只给了一个文件**：按正常批量流程处理（只派发 1 个 agent），不回退到直接调用 `fuwari-post`（保持批量入口的一致性）
