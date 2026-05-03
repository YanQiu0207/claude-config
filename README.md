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
| **download-source** | 多源内容下载工具：把任意 URL（含付费墙网页、微信公众号、X/Twitter、YouTube、小宇宙/喜马拉雅/B 站播客）或本地文件（PDF、EPUB、Word、PPT、Excel、图片、音频、ZIP、CSV/JSON/XML、Markdown）下载/转换为本地 Markdown 或字幕文件，统一落到 `E:/work/downloads/` 目录。 |
| **english-learn** | 当用户给出一句英文并要求「解析、分析、拆句、提炼范式、总结句型、有没有套路、能不能用到其它地方」时触发。 |
| **fuwari-post** | 将一个 Markdown 源文件迁移到 Fuwari 博客的 posts 目录，并完成图片本地化和 frontmatter 生成。 |
| **google-cpp-naming** | 【知识库】Google C++ 命名规范。生成、修改、审查或解释 C++ 代码时，如用户要求 Google C++ 风格，或需要统一 class、struct、变量、成员、常量、函数、namespace、enum、template 参数、macro 的命名风格时启用。 |
| **handoff** | 总结当前对话的日志，写入一个指定文件，方便跨会话传递上下文。 |
| **kms-deep-search** | 知识库深度检索技能：LLM 规划关键词，通过最多 2 轮 Grep 在本地知识库目录直接搜索，阅读命中文章原文（文章较多时派发后台 agent 并行摘要），最终生成带行号引用的回答。 |
| **kms-knowledge-assistant** | Use when the assistant should answer user questions from the local personal knowledge base as a normal working skill, not as an API test. |
| **learn-repo** | 源码驱动的方式独立学习一个开源项目，产出 5 份带 file:line 引用的学习文档（定位/架构/主线/why/gap）。 |
| **md-fmt** | 对单个 Markdown 文件进行一站式标准化：先排版规范化，再网络图片本地化。 |
| **md-img-local** | 将 Markdown 文件中的网络图片自动下载到本地 assets 目录，添加唯一前缀避免重名冲突，自动替换原文件中的图片链接为本地相对路径。 |
| **md-lint** | 检查 Markdown 文件的排版是否符合指定规范文件，自动修复问题并输出总结。 |
| **md-zh** | 【知识库】中文 Markdown 排版规范，供 md-lint、md-fmt 等技能内部引用。 |
| **pdf2md** | 将 PDF 忠实转换为 Markdown，最大限度保留原文内容、顺序、层级、列表、链接、图示位置与页面信息。 |
| **project-launch-audit** | Audit a repository, design package, or new project for launch readiness. |
| **qiaomu-anything-to-notebooklm** | 多源内容智能处理器：支持微信公众号、网页、YouTube、播客（小宇宙/喜马拉雅）、PDF、Markdown 等，自动上传到 NotebookLM 并生成播客/PPT/思维导图等多种格式。 |
| **resume-reviewing** | 用于检查、润色和优化简历内容，提升表达质量。 |
| **skill-del** | 安全删除 skill，自动扫描并处理所有依赖关系（其他 skill、agent 中的引用），确保删除后系统一致。 |
| **skill-rename** | 为 skill 改名，同时自动检查和更新所有依赖关系。 |

## Agents 列表

| Agent | 说明 |
|-------|------|
| **fuwari-post-worker** | 对单个 Markdown 文件执行 Fuwari 博客迁移（复制、frontmatter 生成、图片本地化），供 batch-fuwari-post 并行调度使用。 |
| **kms-article-summarizer** | 阅读单篇知识库文章，提取与问题相关的内容并精确标注行号，供 kms-deep-search 并行调度使用。 |
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
| **markdown-zh.md** | 中文文案排版指南，定义中英混排、标点、空格等规范。 | `md-zh` |
| **claude-code-guide.md** | Claude Code 使用技巧汇总，供 CLAUDE.md 中的知识库查询指令引用。 | CLAUDE.md |

## 全局指令（CLAUDE.md）

Claude Code 的全局行为配置，涵盖：称呼约定（统一称用户为「老板」）、沟通方式（优先中文，直角引号，英文模式下先提供标准英文标注）、事实性内容必须有来源支撑（写入文档须附来源链接，来源不明不得落盘）、通用代码风格（4 空格缩进）、Claude Code 参考知识库路径（`~/.claude/claude_ref/claude-code-guide.md`）、中文 Markdown 排版规范（通过 `md-zh` 技能，写入前必须自检、写入后须复核）、记忆与知识写入规则（全局 vs. 项目的持久化位置）、创建或修改技能时先调用 `cc-adv-guide`、编程规则（编码前不假设不隐藏困惑、简洁优先、精准修改只碰必须碰的、目标驱动执行循环验证）。安装时注意不要覆盖本地已有的 `CLAUDE.md`，应手动合并。

## 目录结构

```text
claude-config/
├── agents/          # Agent 定义
├── claude_ref/      # 参考文件（排版规范、知识库等）
├── scripts/         # 辅助脚本（路径同步、KMS 工具等）
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

google-cpp-naming ── （知识库，无依赖）

kms-knowledge-assistant ── （独立，无依赖）

learn-repo ──────────── （独立，无依赖）

kms-deep-search ────── kms-article-summarizer (agent)

project-launch-audit ── （独立，内置 references/ 检查清单，无外部依赖）

qiaomu-anything-to-notebooklm ── （独立，无依赖）

english-learn ──────── md-zh (skill)

download-source ─────── （独立，无依赖）
```

- `md-lint` 依赖 `md-zh` skill（中文排版规范知识库）；`md-fmt` 依赖 `md-lint` 和 `md-img-local` skill。
- `batch-md-fmt` 通过 `md-fmt-worker` agent 并行调用 `md-fmt`。
- `batch-md-lint` 通过 `md-lint-worker` agent 并行调用 `md-lint`。
- `resume-reviewing` 依赖 `resume-reviewer` agent 进行简历审核。
- `batch-fuwari-post` 通过 `fuwari-post-worker` agent 并行调用 `fuwari-post`；`fuwari-post` 独立使用，无 skill 依赖。
- `code-review-local` 通过 5 个 reviewer agent 并行审查 CLAUDE.md 合规、bug、安全、质量、测试五个维度。
- `kms-deep-search` 通过 `kms-article-summarizer` agent 并行摘要命中文章（文章数 > 3 时），直接使用 Grep/Read 操作文件系统，不调用 KMS HTTP 接口。
- `english-learn` 依赖 `md-zh` skill（中文排版规范知识库）。
- `md-zh`、`cc-adv-guide`、`google-cpp-naming` 为知识库型 skill，无依赖，由其他 skill 或 CLAUDE.md 引用调用；其余 skill（`download-source`、`fuwari-post`、`handoff`、`kms-knowledge-assistant`、`learn-repo`、`md-img-local`、`pdf2md`、`project-launch-audit`、`qiaomu-anything-to-notebooklm`、`skill-del`、`skill-rename`）可独立使用。

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

## KMS 索引刷新脚本

仓库内提供了 `scripts/refresh_kms_index.py`，用于手动调用本地 `kms-api` 的 `/index` 接口，并顺带检查 `/health`、回读 `/stats`。

运行方式：

```bash
python scripts/refresh_kms_index.py
python scripts/refresh_kms_index.py --mode full
```

可选参数：

- `--base-url`：覆盖默认地址，默认值为 `http://127.0.0.1:49153`
- `--timeout`：设置 HTTP 超时秒数
- `--skip-stats`：只触发索引，不回读 `/stats`

## KMS 探测脚本

仓库内提供了 `scripts/probe_kms_api.py`，用于探测本地 `kms-api` 是否在线；默认检查 `/health` 和 `/stats`。

运行方式：

```bash
python scripts/probe_kms_api.py
python scripts/probe_kms_api.py --skip-stats
```

可选参数：

- `--base-url`：覆盖默认地址，默认值为 `http://127.0.0.1:49153`
- `--timeout`：设置 HTTP 超时秒数
- `--skip-stats`：只探测 `/health`

## 邮件发送模块

仓库内提供了 `scripts/send_email.py`，配置驱动的邮件发送模块，推荐配合 QQ 邮箱 SMTP 服务使用。支持纯文本、HTML、抄送/密送、异步批量发送，内置每小时 10 封 / 每天 100 封的频率限制。

配置文件为脚本同目录的 `email_config.json`（格式参考 `email_config.example.json`）。

命令行用法：

```bash
python scripts/send_email.py --to foo@example.com --subject "标题" --body "正文"
python scripts/send_email.py --to foo@example.com --subject "标题" --body-file body.txt --html
```

可选参数：

- `--to`：收件人地址（可多次指定）
- `--cc`：抄送地址（可多次指定）
- `--bcc`：密送地址（可多次指定）
- `--html`：正文按 HTML 格式处理
- `--config`：指定配置文件路径

也可作为模块导入，供其他脚本（如 `collect_server_stats.py`）调用。

## 服务器状态采集脚本

仓库内提供了 `scripts/collect_server_stats.py`，采集当前时刻的 CPU、内存、磁盘分区与磁盘 I/O 情况，生成 HTML 报告并通过 `send_email.py` 发送到指定邮箱。适合挂到定时任务执行。

依赖：

```bash
pip install psutil matplotlib
```

运行方式：

```bash
python scripts/collect_server_stats.py --to you@example.com
python scripts/collect_server_stats.py --to foo@example.com --subject "今日巡检"
```

可选参数：

- `--to`：收件人地址
- `--subject`：邮件主题
- `--config`：邮件配置文件路径
- `--io-interval`：磁盘 I/O 采样窗口秒数
- `--require-disk-io`：磁盘 I/O 采集失败时直接退出（默认降级继续）
