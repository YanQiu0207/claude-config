---
name: project-init
description: |
  初始化当前项目：选择版本管理模式（纯 git，或本地 git + 提交走 SVN）、git init、
  创建 .gitignore / CLAUDE.md / AGENTS.md / README.md / docs 目录骨架，接线跨项目共用知识库，并打首次提交。
  版本管理模式写入 AGENTS.md，保证每次会话强制加载。已存在的文件一律跳过，不覆盖。
  仅通过 /project-init 手动触发，禁止模型自动调用。
disable-model-invocation: true
---

> 输出一行：`Using project-init`

# 项目初始化

作用于当前工作目录，无参数。所有步骤遵循同一原则：**已存在的内容跳过，不覆盖、不改写**。

## 处理流程

### 1. 选择版本管理模式

向用户提问（单选），拿到答案前不执行后续步骤：

- **纯 git**：git 同时用于本地开发和正式提交
- **git + SVN**：本地用 git（方便 AI 并行开发，如 worktree、分支），正式提交走 SVN

### 2. git 初始化

两种模式都需要 git。运行 `git rev-parse --is-inside-work-tree` 判断：

- 已是仓库 → 跳过，记录「已存在」
- 不是仓库 → 运行 `git init`，记录「已初始化」
- `git init` 失败 → 报告错误，继续执行后续文件创建步骤

### 3. 创建 .gitignore

不存在则创建，已存在则只补缺失条目（用追加，不动已有内容）：

```gitignore
# OS / 编辑器
.DS_Store
Thumbs.db

# AI 客户端本地配置
.claude/settings.local.json
```

git + SVN 模式额外加一条 `.svn/`。

### 4. SVN 忽略配置（仅 git + SVN 模式）

运行 `svn info` 判断当前目录是否为 SVN 工作副本：

- **是工作副本**（checkout 过即可，不要求提交过）→ 运行 `svn propset svn:ignore` 把 `.git` 与 `.gitignore` 加入忽略（先 `svn propget svn:ignore` 读出已有值，合并后写回）。属性修改本地立即生效，随用户下一次 `svn commit` 入库
- **不是工作副本** → 无法设置属性（`svn propset` 对未版本化目录会失败），跳过；在汇总报告和 AGENTS.md 版本管理章节中注明「接入 SVN 后需补 `svn propset svn:ignore`」
- 机器未安装 svn 命令 → 同上处理

### 5. 判断项目类型

扫描当前目录（排除 `.git/`、`.svn/`、`node_modules/` 等依赖目录）：

- 除本 skill 要创建的文件外没有其他实质文件 → **空项目**
- 存在代码或文档等实质内容 → **已有代码项目**

### 6. 创建 CLAUDE.md

若已存在则跳过。否则写入一行：

```markdown
@AGENTS.md
```

规则集中在 AGENTS.md：Claude Code 经 CLAUDE.md 引用加载，Codex 原生加载 AGENTS.md，两个客户端每次会话都会读到同一份规则。

### 7. 创建 AGENTS.md

**版本管理章节**按所选模式生成。

纯 git 模式：

```markdown
## 版本管理（强制）

- 本项目使用 git 管理版本
```

git + SVN 模式：

```markdown
## 版本管理（强制）

- 本地开发使用 git：分支、worktree 并行开发均基于 git
- 正式提交只走 SVN（`svn commit`），**禁止 git push**
- `.svn/` 不入 git，`.git/` 与 `.gitignore` 不入 SVN
```

写入规则：

- 不存在 → 写入骨架 + 版本管理章节：

```markdown
# 项目规则

<版本管理章节>

## 文档规则

- TODO

## 代码规则

- TODO
```

- 已存在且无「版本管理」章节 → 追加版本管理章节，其余内容不动
- 已存在且已有「版本管理」章节 → 跳过，报告中注明

除版本管理章节外，不要自行编造规则填入，内容由用户后续补充。

### 8. 创建 README.md

若已存在则跳过。否则按项目类型生成：

**空项目** → 占位骨架（`<项目名>` 取当前目录名）：

```markdown
# <项目名>

TODO: 一句话简介。

## 用法

TODO

## 目录结构

TODO
```

**已有代码项目** → 先读取目录结构和关键文件（构建配置、入口文件等），生成：

- 项目名 + 一句话简介（依据实际代码得出，不确定时写 TODO，禁止编造）
- 用法（仅在能从构建配置确认命令时填写，否则写 TODO）
- 目录结构（仅列一级目录及职责）

### 9. 创建 docs 目录骨架

按 `project-knowledge` 的目录约定创建（已存在的目录跳过）：

```
docs/
├── design-docs/      # Feature Spec（spec.md / tasks.md）
├── arch-snapshots/   # 架构快照
├── adr/              # 架构决策记录
└── issues/           # 已查证的故障与踩坑
```

每个空目录放一个 `.gitkeep` 占位（git 不跟踪空目录）。

### 10. 跨项目共用知识库接线

在 `~/.claude/CLAUDE.md` 中查找「## 跨项目共用知识库」章节记录的路径。该文件是知识库路径的唯一权威位置：

- **有有效路径** → 直接用该路径执行接线，不再询问
- **无有效路径** → 询问用户（单选）：
  - 提供跨项目共用知识库路径 → 在 `~/.claude/CLAUDE.md` 末尾追加「## 跨项目共用知识库」章节记录该路径，再执行接线
  - 暂无跨项目共用知识库 → 跳过本步，报告中注明

**接线**：AGENTS.md 已有「知识库」章节则跳过；否则追加：

```markdown
## 知识库

- 跨项目共用知识库位于 `<path>`（跨项目方法论 `domains/`、踩坑 `issues/`、原始资料 `sources/`）
- 需求澄清、方案设计、编码实现、排查 bug 前，先查其根 `index.md`，两跳定位到条目，禁止全库通配检索
- 产生跨项目可复用的结论时，归档进该库并更新索引
```

### 11. 首次 git commit

仅提交**本次 skill 创建或修改的文件**（`git add` 逐个指定路径，不用 `git add .`，避免卷入用户已有的未跟踪文件），提交信息：

```
chore: 初始化项目脚手架
```

- 本次未创建任何文件 → 跳过
- git + SVN 模式 → 只提交到本地 git，不做任何 push；`svn commit` 由用户自行决定

### 12. 汇总报告

```markdown
| 项目 | 结果 |
| --- | --- |
| 版本管理模式 | 纯 git / git + SVN |
| git | 已初始化 / 已存在 |
| SVN 忽略 | 已设置 / 非工作副本（待接入后补） / 不适用 |
| .gitignore | 已创建 / 已补条目 / 已存在（跳过） |
| CLAUDE.md | 已创建 / 已存在（跳过） |
| AGENTS.md | 已创建 / 已追加版本管理章节 / 已存在（跳过） |
| README.md | 已创建（骨架 / 自动生成） / 已存在（跳过） |
| docs 骨架 | 已创建 / 已存在（跳过） |
| 跨项目共用知识库接线 | 已接线 / 已存在（跳过） / 暂无（跳过） |
| 首次提交 | 已提交 / 跳过 |
```

## 边界情况

- 所有产物都已存在且 AGENTS.md 已有版本管理章节 → 不做任何修改，直接报告「无需初始化」
- 生成的中文 Markdown 须遵循 md-zh 排版规范（中英文空格、中文与数字空格、全角标点）
