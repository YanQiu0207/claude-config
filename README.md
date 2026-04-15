# Claude Code Config

个人 Claude Code 配置同步仓库，包含自定义的 Skills、Agents、参考文件和全局指令。

## Skills 列表

| Skill | 说明 |
|-------|------|
| **batch-fuwari-post** | 批量将多个 Markdown 文件/目录迁移到 Fuwari 博客的 posts 目录，每篇以独立子目录组织（`posts/<slug>/index.md` + 同目录图片），并生成 frontmatter。 |
| **batch-md-fmt** | 批量对多个 Markdown 文件进行一站式标准化：先排版规范化，再网络图片本地化。 |
| **batch-md-lint** | 批量检查多个 Markdown 文件的排版规范。 |
| **cc-adv-guide** | 【知识库】Claude Code 进阶指南，包含 Skills 与 Agents 的高级用法和设计模式。 |
| **code-review-local** | 对本地代码目标（文件 / 目录 / 整个项目）进行多 agent 并行审核。 |
| **fuwari-post** | 将一个 Markdown 源文件迁移到 Fuwari 博客的 posts 目录，并完成图片本地化和 frontmatter 生成。 |
| **handoff** | 总结当前对话的日志，写入一个指定文件，方便跨会话传递上下文。 |
| **kms-knowledge-assistant** | Use when Codex should answer user questions from the local personal knowledge base as a normal working skill, not as an API test. |
| **md-fmt** | 对单个 Markdown 文件进行一站式标准化：先排版规范化，再网络图片本地化。 |
| **md-img-local** | 将 Markdown 文件中的网络图片自动下载到本地 assets 目录，添加唯一前缀避免重名冲突，自动替换原文件中的图片链接为本地相对路径。 |
| **md-lint** | 检查 Markdown 文件的排版是否符合指定规范文件，自动修复问题并输出总结。 |
| **md-zh** | 【知识库】中文 Markdown 排版规范，供 md-lint、md-fmt 等技能内部引用。 |
| **pdf2md** | 将 PDF 忠实转换为 Markdown，最大限度保留原文内容、顺序、层级、列表、链接、图示位置与页面信息。 |
| **resume-reviewing** | 用于检查、润色和优化简历内容，提升表达质量。 |
| **skill-del** | 安全删除 skill，自动扫描并处理所有依赖关系（其他 skill、agent 中的引用），确保删除后系统一致。 |
| **skill-rename** | 为 skill 改名，同时自动检查和更新所有依赖关系。 |

## Agents 列表

| Agent | 说明 |
|-------|------|
| **fuwari-post-worker** | 对单个 Markdown 文件执行 Fuwari 博客迁移（复制、frontmatter 生成、图片本地化），供 batch-fuwari-post 并行调度使用。 |
| **md-fmt-worker** | 对单个 Markdown 文件执行一站式标准化处理（排版 + 图片本地化），供 batch-md-fmt 并行调度使用。 |
| **md-lint-worker** | 对单个 Markdown 文件执行排版检查与修复，供 batch-md-lint 并行调度使用。 |
| **resume-reviewer** | 审核和评估简历，并提供修改建议。 |
| **reviewer-bug** | 对指定代码目标（文件/目录/项目）进行 bug 与逻辑缺陷审核，只报告明显的功能性缺陷。 |
| **reviewer-compliance** | 对指定代码目标（文件/目录/项目）进行 CLAUDE.md 合规性审核，仅报告违反 CLAUDE.md 规则的代码。 |
| **reviewer-quality** | 对指定代码目标（文件/目录/项目）进行代码质量与可维护性审核，关注重复、复杂度、耦合、命名、抽象。 |
| **reviewer-security** | 对指定代码目标（文件/目录/项目）进行安全漏洞审核，对照 OWASP Top 10 等常见漏洞类别。 |
| **reviewer-test** | 对指定代码目标（文件/目录/项目）进行测试覆盖与可测性审核，关注关键路径是否有测试、测试是否真正验证行为、生产代码是否易测试。 |

## 参考文件（claude_ref）

Skills 运行时引用的规范和知识库文件，安装对应 skill 时需一并安装。

| 文件 | 说明 | 被引用方 |
|------|------|----------|
| **markdown-zh.md** | 中文文案排版指南，定义中英混排、标点、空格等规范。 | — |
| **claude-code-guide.md** | Claude Code 使用技巧汇总，供 CLAUDE.md 中的知识库查询指令引用。 | CLAUDE.md |

## 全局指令（CLAUDE.md）

Claude Code 的全局行为配置，涵盖：称呼约定（统一称用户为「靓仔」）、沟通语言（中文）、事实性内容必须有来源支撑的要求、任务分流（单文件小修直接执行，多文件多阶段任务按阶段制走）、工程强制规则（日志完整性、防腐层、参数可配置、敏感信息脱敏等）、协作底线（多 agent 分工与进度表述规范）、写代码前必须先确认设计方案与开发计划、代码风格（4 空格缩进）、Claude Code 参考知识库路径、中文 Markdown 排版规范（通过 `md-zh` 技能）、记忆与知识写入规则（全局 vs. 项目的持久化位置）、创建或修改技能时先调用 `cc-adv-guide`、复杂项目按模板在 `dev-run/` 下建立治理文档。安装时注意不要覆盖本地已有的 `CLAUDE.md`，应手动合并。

## 目录结构

```text
claude-config/
├── agents/          # Agent 定义
├── claude_ref/      # 参考文件（排版规范、知识库等）
├── scripts/         # 路径同步脚本
├── skills/          # 技能定义
├── .ai-rules/       # AI 辅助规则（交付工作流、工程规范等）
├── .githooks/       # Git 钩子配置（开发用）
├── .gitignore       # Git 忽略规则
└── CLAUDE.md        # 全局指令
```

## 安装方式

将仓库中的文件复制到 `~/.claude/` 对应目录下即可。

### 完整安装

```bash
git clone <repo-url> claude-config
cd claude-config

cp -r skills/* ~/.claude/skills/
cp -r agents/* ~/.claude/agents/
cp -r claude_ref/* ~/.claude/claude_ref/
cp -r .ai-rules/* ~/.ai-rules/

# CLAUDE.md 包含全局指令，本地已有则不要覆盖，请手动合并
cp -n CLAUDE.md ~/.claude/CLAUDE.md
```

Windows（PowerShell）：

```powershell
git clone <repo-url> claude-config
cd claude-config

Copy-Item -Recurse skills\* $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse agents\* $env:USERPROFILE\.claude\agents\
Copy-Item -Recurse claude_ref\* $env:USERPROFILE\.claude\claude_ref\
Copy-Item -Recurse .ai-rules\* $env:USERPROFILE\.ai-rules\

# CLAUDE.md 包含全局指令，本地已有则不要覆盖，请手动合并
if (-not (Test-Path $env:USERPROFILE\.claude\CLAUDE.md)) {
    Copy-Item CLAUDE.md $env:USERPROFILE\.claude\CLAUDE.md
} else {
    Write-Warning "~/.claude/CLAUDE.md 已存在，请手动合并"
}
```

### 按需安装

只安装单个 skill 时，注意同时安装它的依赖（参见下方依赖关系）。

```bash
# 示例：只安装 md-fmt 及其依赖
cp -r claude-config/skills/md-fmt ~/.claude/skills/
cp -r claude-config/skills/md-lint ~/.claude/skills/
cp -r claude-config/skills/md-img-local ~/.claude/skills/
cp -r claude-config/skills/md-zh ~/.claude/skills/
```

## 依赖关系

```text
md-fmt ─────────┬── md-lint (skill)
                └── md-img-local (skill)

md-lint ────────── md-zh (skill)

md-zh ──────────── （知识库，无依赖）

batch-md-fmt ───── md-fmt-worker (agent)
                       └── md-fmt (skill，含上述依赖)

batch-md-lint ──── md-lint-worker (agent)
                       └── md-lint (skill，含上述依赖)

resume-reviewing ── resume-reviewer (agent)

fuwari-post ─────── （独立，无依赖）

batch-fuwari-post ── fuwari-post-worker (agent)
                         └── fuwari-post (skill)

code-review-local ─┬── reviewer-compliance (agent)
                   ├── reviewer-bug (agent)
                   ├── reviewer-security (agent)
                   ├── reviewer-quality (agent)
                   └── reviewer-test (agent)

cc-adv-guide ────── （知识库，无依赖）

kms-knowledge-assistant ── （独立，无依赖）
```

- `md-lint` 依赖 `md-zh` skill（中文排版规范知识库）；`md-fmt` 依赖 `md-lint` 和 `md-img-local` skill。
- `batch-md-fmt` 通过 `md-fmt-worker` agent 并行调用 `md-fmt`。
- `batch-md-lint` 通过 `md-lint-worker` agent 并行调用 `md-lint`。
- `resume-reviewing` 依赖 `resume-reviewer` agent 进行简历审核。
- `batch-fuwari-post` 通过 `fuwari-post-worker` agent 并行调用 `fuwari-post`；`fuwari-post` 独立使用，无 skill 依赖。
- `code-review-local` 通过 5 个 reviewer agent 并行审查 CLAUDE.md 合规、bug、安全、质量、测试五个维度。
- `md-zh`、`cc-adv-guide` 为知识库型 skill，无依赖，由其他 skill 或 CLAUDE.md 引用调用；其余 skill（`fuwari-post`、`handoff`、`kms-knowledge-assistant`、`md-img-local`、`pdf2md`、`skill-del`、`skill-rename`）可独立使用。

## 开发设置

克隆后启用 pre-commit hook，避免敏感信息被误提交：

```bash
git config core.hooksPath .githooks
cp .githooks/sensitive-patterns.example .githooks/sensitive-patterns
# 编辑 sensitive-patterns，填入你自己的敏感信息模式
```

## 使用注意

- `resume-reviewing` skill 的 `SKILL.md` 可能包含个人求职背景信息，使用前请按自己的情况修改。
- `resume-reviewer` agent 同理，使用前请根据自己的情况调整 prompt 内容。

## 路径同步脚本

仓库内提供了 `scripts/sync-paths.py`，用于按映射规则将任意本地目录或文件单向同步到当前仓库。

同步配置位于 `scripts/sync-pathmap.json`，脚本会按配置中的顺序依次执行同步。每条映射包含以下字段：

```json
{
  "mappings": [
    {
      "source": "~/source/dir-a",
      "target": "dir-a"
    },
    {
      "source": "~/source/dir-b",
      "target": "dir-b"
    },
    {
      "source": "~/source/config.md",
      "target": "config.md"
    }
  ]
}
```

- `enabled`：可选，是否启用该映射；默认值为 `true`。当值为 `false` 时，脚本会跳过该映射。
- `source`：源目录或源文件，支持 `~`、环境变量和绝对路径。
- `target`：仓库内的目标目录或目标文件，推荐写仓库相对路径。
- 目录到目录：递归同步目录内文件。
- 文件到文件：同步单个文件。

同步规则：

- 源文件比目标文件新时，覆盖目标文件。
- 目标文件比源文件新时，不覆盖，记为冲突。
- 源侧文件已删除时，同步删除目标侧对应的文件。
- 有变更时自动执行 `git add`、`git commit`、`git push`。

运行方式：

```bash
python scripts/sync-paths.py
```

如果只需要暂时停用某条同步规则，将对应映射的 `enabled` 设为 `false` 即可，无需改 Python 脚本。
