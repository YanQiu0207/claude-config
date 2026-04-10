# Claude Code Config

个人 Claude Code 配置同步仓库，包含自定义的 Skills 和 Agents。

## Skills 列表

| Skill | 说明 |
|-------|------|
| **batch-md-lint** | 批量检查 Markdown 文件质量 |
| **md-zh** | Markdown 中文排版规范（中英文空格、全角标点、专有名词大小写等） |
| **md-img-local** | 将 Markdown 中的网络图片下载到本地 `assets/` 目录并替换链接 |
| **md-fmt** | 一站式 Markdown 标准化：先做中文排版规范化，再做图片本地化 |
| **pdf2md** | 将 PDF 忠实转换为 Markdown，尽量保留原文内容和结构 |
| **resume-reviewing** | 简历审校与优化建议 |
| **skill-rename** | 安全地重命名 skill，并同步更新相关引用 |

## Agents 列表

| Agent | 说明 |
|-------|------|
| **md-lint** | 检查 Markdown 文件排版是否符合 md-zh 规范，自动修复并输出检查报告 |
| **resume-reviewer** | 审核和评估简历，从多维度提供详细的优化建议 |

## 安装方式

将需要的 skill / agent 目录或文件复制到 `~/.claude/` 对应目录下即可：

```bash
# 克隆仓库
git clone <repo-url> claude-config

# 复制单个 skill
cp -r claude-config/skills/md-zh ~/.claude/skills/

# 复制全部 skills
cp -r claude-config/skills/* ~/.claude/skills/

# 复制全部 agents
cp -r claude-config/agents/* ~/.claude/agents/
```

Windows 用户：

```powershell
# 复制单个 skill
Copy-Item -Recurse claude-config\skills\md-zh $env:USERPROFILE\.claude\skills\

# 复制全部 skills
Copy-Item -Recurse claude-config\skills\* $env:USERPROFILE\.claude\skills\

# 复制全部 agents
Copy-Item -Recurse claude-config\agents\* $env:USERPROFILE\.claude\agents\
```

## 依赖关系

```text
md-fmt
├── md-zh
└── md-img-local
```

- `md-fmt` 依赖 `md-zh` 和 `md-img-local`，使用前需要同时安装这两个 skill。
- 其他 skill 可以独立使用。

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
      "enabled": true,
      "source": "~/.claude/skills/md-zh",
      "target": "md-zh"
    },
    {
      "enabled": false,
      "source": "~/.claude/skills/shared/prompt.md",
      "target": "docs/prompt.md"
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
- 仅做单向同步，不删除仓库中已有但源侧不存在的文件。
- 有变更时自动执行 `git add`、`git commit`、`git push`。

运行方式：

```bash
python scripts/sync-paths.py
```

如果只需要暂时停用某条同步规则，将对应映射的 `enabled` 设为 `false` 即可，无需改 Python 脚本。
