# Claude Code 使用技巧

## 会话管理

### 恢复最近的会话

```bash
claude --continue
```

自动恢复最近一次的会话，包括完整的对话历史。

### 恢复指定会话

```bash
claude --continue <session-id>
```

### 列出所有会话

在 Claude Code 中输入：

```
/resume
```

不带任何参数时，会打开会话选择器，列出当前目录下所有可用的会话供你选择。也可以通过 `/resume <name 或 id>` 恢复指定会话。

### 分叉会话

```bash
claude --continue --fork-session
```

基于之前的对话创建一个新会话，原会话不受影响。适合从同一起点尝试不同方案。

### 其他会话相关命令

| 命令 | 说明 |
| --- | --- |
| `/rename [name]` | 给当前会话命名，方便后续查找 |
| `/branch` 或 `/fork` | 从当前对话创建一个分支 |
| `/stats` | 查看会话使用统计 |

### `/clear` 不会删除会话

`/clear` 只是清除当前上下文窗口中的对话内容，释放上下文空间。对话历史仍然保存在本地的 JSONL 文件中（`~/.claude/projects/` 目录下），不会删除任何数据。

执行过 `/clear` 后，仍然可以通过 `claude --continue <session-id>` 或 `/resume` 恢复完整的对话历史（包括 `/clear` 之前的内容）。

### 会话存储位置

所有会话数据保存在 `~/.claude/projects/` 目录下，以 JSONL 格式存储。如需永久删除会话，需手动删除对应文件。

> 注意：恢复会话时，之前授予的权限不会继承，需要重新授权。

## Plan 模式

进入 Plan 模式的两种方式：

1. **快捷键**：按 `Shift+Tab` 切换（再按一次切换回正常模式）
2. **输入提示词**：在消息中包含 "plan" 相关的词

Plan 模式下只进行研究和分析，不会修改任何文件，适合动手前先理清思路。

## Subagent（自定义子代理）

### 创建 Subagent

在项目的 `.claude/agents/` 目录下创建 Markdown 文件，例如 `.claude/agents/code-reviewer.md`：

```markdown
---
name: code-reviewer
description: 代码审查专家。审查代码的质量、安全性和可维护性
tools: Read, Grep, Glob, Bash
model: sonnet
---

你是一个资深代码审查员。

当被调用时：
1. 运行 git diff 查看最近的更改
2. 关注修改的文件
3. 提供具体、可执行的反馈
```

### 关键配置字段

| 字段 | 说明 |
| --- | --- |
| `name` | 唯一标识符 |
| `description` | 描述（Claude 据此决定何时自动委托任务） |
| `tools` | 允许使用的工具白名单 |
| `disallowedTools` | 禁用的工具黑名单 |
| `model` | 使用的模型：`opus`/`sonnet`/`haiku` |
| `maxTurns` | 最大回合数 |
| `isolation` | 设为 `worktree` 在独立 git worktree 中运行 |
| `memory` | 持久内存作用域：`user`/`project`/`local` |

### 调用方式

```bash
# 查看所有可用 subagent
claude agents

# 作为主线程启动
claude --agent code-reviewer

# 在对话中 @mention
@code-reviewer 审查这个文件
```

也可以在 `.claude/settings.json` 中设为项目默认 agent：

```json
{ "agent": "code-reviewer" }
```

### 作用域

| 位置 | 作用域 |
| --- | --- |
| `.claude/agents/` | 项目级（推荐） |
| `~/.claude/agents/` | 用户级（所有项目可用） |

### 关键配置：`permissionMode`

`permissionMode` 控制 subagent 的权限行为：

| 值 | 说明 |
| --- | --- |
| `default` | 每次工具调用都需用户确认 |
| `acceptEdits` | 自动批准文件编辑，其他需确认 |
| `bypassPermissions` | 跳过所有权限弹窗，自动执行 |

**重要：后台 agent 的 `permissionMode` 必须写在 agent 定义文件的 frontmatter 中。** 通过 Agent 工具调用时的 `mode` 参数传入，在后台运行（`run_in_background: true`）场景下不生效，会导致文件写入、Bash 执行等操作被权限拒绝。

正确写法（agent 定义文件）：

```yaml
---
name: my-worker
permissionMode: bypassPermissions
---
```

错误写法（调用时传入，后台场景无效）：

```
Agent({
  mode: "bypassPermissions",
  run_in_background: true,
  prompt: "..."
})
```

### 关键配置：`skills`

subagent 需要调用 skill 时，必须在 agent 定义文件的 frontmatter 中通过 `skills` 字段声明依赖。未声明的 skill 无法使用。

```yaml
---
name: my-worker
tools:
  - Read
  - Edit
  - Skill
skills:
  - md-fmt
  - md-zh
---
```

### 最佳实践

- **一个 subagent 只做一件事**，保持职责单一
- 通过 `tools` 限制权限，提高安全性
- 细化 `description`，让 Claude 知道何时自动委托

## Skill 的 `context: fork` 选项

在 SKILL.md 的 frontmatter 中可以配置 `context: fork`，让技能在**隔离的子代理环境**中运行，而不是在当前对话上下文中执行。

```yaml
---
name: deep-research
description: Research a topic thoroughly
context: fork
agent: Explore
---
```

- 子代理**无法访问**对话历史，技能内容本身成为驱动子代理的提示词
- `agent` 字段可指定子代理类型：`Explore`、`Plan`、`general-purpose`，或自定义 agent
- 技能必须包含**明确的任务指示**，纯指导原则类的技能用 `context: fork` 没有意义

### 什么时候需要用

大多数 skill 不需要 `context: fork`。典型场景是：**不希望当前对话上下文影响 skill 的判断**，比如每次从零开始独立评估的代码审查 skill。

但这些场景用 Agent 工具 + `run_in_background: true` + worker agent 也能达到类似效果（即三层架构模式）。`context: fork` 更像是一个轻量级替代方案——不用单独写 agent 定义文件，直接在 skill 里声明隔离运行。

## Skill 批量执行设计模式

当一个 skill 需要支持批量（多文件）执行时，采用三层架构：

```
batch-xxx（skill）──调度层
  └─ xxx-worker（agent）──配置层
       └─ xxx（skill）──执行层
```

### 各层职责

| 层级 | 类型 | 职责 |
| --- | --- | --- |
| **调度层** `batch-xxx` | Skill | 文件列表展开（Glob）、并行分发 Agent、汇总报告 |
| **配置层** `xxx-worker` | Agent | 声明 `permissionMode`、`tools`、`skills`、`model`，调用执行层技能 |
| **执行层** `xxx` | Skill | 单文件的实际处理逻辑 |

### 为什么需要三层

- **调度层和执行层分离**：单文件 skill 可独立使用，批量 skill 只负责编排，不重复业务逻辑
- **配置层（agent）不可省略**：后台 agent 的 `permissionMode` 必须写在 agent 定义文件中才能生效；同时 agent 需要通过 `skills` 字段声明依赖的技能

### 调度层模板（`batch-xxx/SKILL.md`）

核心流程：

1. **确定文件列表**：Glob 展开通配符，或逐个确认路径存在
2. **并行分发**：在同一条消息中发起多个 Agent 调用
   - `subagent_type: "xxx-worker"`
   - `run_in_background: true`
   - prompt 中写明文件**绝对路径**（subagent 是独立上下文，看不到主对话）
   - 同时并行不超过 8 个，超过时分批
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

### 配置层模板（`agents/xxx-worker.md`）

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

### 并发安全

#### 检查清单

执行层 skill 必须确保并发安全：

- 不使用固定名称的临时文件（用 `mktemp` 或 PID 后缀）
- 不依赖共享的全局状态
- 每个文件的产出路径互不冲突（如用文件名前缀区分）

#### 标注义务

凡是会被 batch 调度层通过多个并行 agent 同时调用的 **skill** 和 **agent**，都必须在文件中添加并发安全说明，提醒后续修改者不要引入共享状态。

**需要标注的层级**：

| 层级 | 文件位置 | 说明 |
| --- | --- | --- |
| 执行层 skill | `skills/xxx/SKILL.md` | 实际执行逻辑，最易引入共享状态冲突 |
| 执行层 skill 调用的下游 skill | 如 `md-img-local` | 被间接并发调用，同样需要标注 |
| 配置层 agent | `agents/xxx-worker.md` | 被并行启动多个实例 |

**标注格式**：

在 frontmatter 之后、正文开头处添加 blockquote：

执行层 skill：

```markdown
> **⚠ 并发安全**：本技能被 `batch-xxx` 通过多个并行 `xxx-worker` agent 同时调用，每个 agent 处理不同文件。修改本技能时，必须确保不引入共享状态（如全局临时文件、固定名称的中间产物等），否则并发执行会产生冲突。
```

配置层 agent：

```markdown
> **⚠ 并发安全**：本 agent 被 `batch-xxx` 并行启动多个实例，每个实例处理不同文件。修改本定义时，确保不引入实例间共享状态。
```

**不需要标注的**：调度层 `batch-xxx` 本身（它是调度方，不会被并发调用）。

### 实际案例

`batch-md-fmt`（调度层）→ `md-fmt-worker`（配置层）→ `md-fmt`（执行层）→ `md-img-local`（下游 skill）

## 工作目录

Claude Code 的主工作目录在启动时由当前目录决定，会话中无法更改。如需切换主项目，应在目标目录重新启动 Claude Code。

### 添加额外工作目录

可以在不改变主工作目录的情况下，扩展文件访问范围：

**启动时添加：**

```bash
claude --add-dir /path/to/other/project
```

**会话中添加：**

```
/add-dir /path/to/other/project
```

**持久化配置（settings.json）：**

```json
{
    "additionalDirectories": ["/path/to/other/project"]
}
```

> 注意：额外目录中的 `.claude/` 配置不会被自动发现。

## 防止个人敏感信息泄露

分享 skill 或提交代码时，容易不小心把个人路径（如 `C:\Users\xxx`）、用户名等信息带进去。可以设置两层防护：

### 第一层：Claude Code Hook（写入时检查）

在 `~/.claude/hooks/` 下创建检查脚本和敏感模式文件：

**`~/.claude/hooks/sensitive-patterns`**（每行一个正则）：

```
C:\\Users\\YourName
/home/yourname
YourName
```

**`~/.claude/hooks/check-sensitive-info.sh`**：

```bash
#!/bin/bash
PATTERNS_FILE="$HOME/.claude/hooks/sensitive-patterns"
[ ! -f "$PATTERNS_FILE" ] && exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ] && exit 0

FOUND=0
while IFS= read -r pattern || [ -n "$pattern" ]; do
    [[ -z "$pattern" || "$pattern" == \#* ]] && continue
    matches=$(grep -inE "$pattern" "$FILE_PATH" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        [ "$FOUND" -eq 0 ] && echo "WARNING: 文件 $FILE_PATH 中检测到敏感个人信息：" && FOUND=1
        echo "  模式 [$pattern]:"
        echo "$matches" | head -5 | sed 's/^/    /'
    fi
done < "$PATTERNS_FILE"

[ "$FOUND" -ne 0 ] && echo "" && echo "请检查并移除上述敏感信息。" && exit 2
```

在 `~/.claude/settings.json` 中注册：

```json
{
    "hooks": {
        "PostToolUse": [
            {
                "matcher": "Write|Edit",
                "hooks": [
                    {
                        "type": "command",
                        "command": "bash ~/.claude/hooks/check-sensitive-info.sh"
                    }
                ]
            }
        ]
    }
}
```

### 第二层：Git Pre-commit Hook（提交时拦截）

在仓库中创建 `.githooks/pre-commit`，从外部模式文件读取正则，扫描暂存区内容，匹配到敏感信息则阻止提交。

关键设计：模式文件（`.githooks/sensitive-patterns`）加入 `.gitignore` 不提交，仓库中只保留 `.githooks/sensitive-patterns.example` 作为模板。

```bash
# 启用 hook
git config core.hooksPath .githooks
cp .githooks/sensitive-patterns.example .githooks/sensitive-patterns
# 编辑填入个人信息模式
```

两层配合：Claude 写文件时**立刻警告**，git commit 时**兜底拦截**。

## Agent Team（多智能体协作）

Agent Team 是 Claude Code 的实验性功能，支持多个智能体并行协作，默认禁用。

### 启用方法

在 `~/.claude/settings.json` 的 `env` 字段中添加：

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

或设置系统环境变量：

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

### 使用方式

启用后用自然语言描述团队即可创建，例如：

> 创建一个 agent team，一个负责前端开发，一个负责后端 API，一个负责写测试。

### 核心特点

- 每个 teammate 有独立 context window，可互相通讯
- 共享任务列表，所有成员可以看到任务状态、认领工作
- 适合研究审查、多模块并行开发、bug 调查、跨层协调等场景

### 注意事项

- 需要 Claude Code v2.1.32+
- 一个会话只能管理一个团队
- 实验性功能，不支持 `/resume` 会话恢复
