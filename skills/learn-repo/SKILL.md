---
name: learn-repo
description: |
  源码驱动的方式独立学习一个开源项目，产出 5 份带 file:line 引用的学习文档（定位/架构/主线/why/gap）。适用于用户给定项目路径，要求「学习」「理解」「摸清」「搞懂」「适配」一个开源项目的架构、原理、实现方式。
  方法特点：先源码后文档、强制代码行号锚定、挖 git log 反推设计动机、最后与官方 docs 对比校验独立结论。
argument-hint: "<项目绝对路径> [depth: quick|standard|deep]"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Bash(git log:*)
  - Bash(git show:*)
  - Bash(ls:*)
  - Bash(wc:*)
  - Bash(mkdir:*)
---

当此 skill 生效时，第一行回答固定写：`Using skill: learn-repo`

# learn-repo · 源码驱动的开源项目学习法

用源码 + git log 独立摸清一个开源项目，产出 5 份带代码引用的学习文档，便于后续理解或适配。此流程已在 `bridgic` 项目实战验证过（见 `E:\github\bridgic\.learn-by-claude\`）。

## 核心原则

1. **事实锚定**：任何事实性声明必须附 `file:line` 或 `commit-hash`。推断必须明确标「推断」「待验证」。
2. **源码优先**：阶段 1-4 严禁读项目内 `docs/` 下的人工总结（防止污染独立判断）；仅阶段 5 对比。
3. **落盘产出**：每阶段必须产出一份 md 文件，不能只在对话里说完就算（上下文会丢）。
4. **目标驱动**：开始前问清学习目标（纯理解 vs 有适配目标），避免漫无目的通读。
5. **深度分层**：用 `quick` / `standard`（默认）/ `deep` 控制工作量，避免失控。

## 输入参数

- 参数 1：项目绝对路径（必需）
- 参数 2：`depth = quick | standard | deep`（可选，默认 `standard`）

## 阶段 0：对齐（开工前）

跟用户确认 3 件事，缺一不可：

1. **项目路径** — 绝对路径，可读
2. **产出位置** — 默认 `<项目>/.learn-by-claude/`；若想避免污染仓库，改到 `<工作目录>/study-<项目名>/`
3. **学习目标** — 纯理解？有具体适配目标？是否关注特定模块？

如果用户已经读过项目 docs 或有先入印象，记下来，阶段 5 时一并对比。

用 `TaskCreate` 建 6 个 task（阶段 1-5 + 可选阶段 6），每阶段开始 in_progress、结束 completed。

## 阶段 1：项目定位（产出 `01-overview.md`）

### 工具

- Read `README.md`、`CHANGELOG.md`（开头部分即可）
- Read 根依赖文件：`pyproject.toml` / `package.json` / `go.mod` / `Cargo.toml` / `build.gradle`
- Glob 子包 README：`**/packages/*/README*`、`**/crates/*/README*`
- （可选）`WebSearch` 对比 1-2 个同类项目，给定位参考

### 产出结构

```
# 01 · 项目定位

## 来源（哪些文件、不看哪些）
## 一句话定位
## 核心理念 / 主张
## 版本与语言（表格：版本、Python/Node 版本、构建、License）
## 包结构（目录树 + 一行职责）
## 关键概念清单（从 README 提炼的核心 API / 原语）
## 与同类对比（我的判断）
## 初步疑问清单（编号，阶段 2-4 去验证）
## 阶段 1 小结
```

### 关键要求

- README 的营销话术要标 `[README 宣称]` / `[待验证]`，不能直接当事实
- 疑问清单编号，阶段 2-4 每次更新「已解答 / 部分 / 未解」状态

## 阶段 2：画模块地图（产出 `02-architecture.md`）

### 工具

- Bash `ls` 各子包内部结构
- Read 每个子包的 `__init__.py` / `index.ts` 看公开 API
- Read 关键类文件**头部**（80 行内，不读全文件）看 imports + 类定义
- Grep `class XXX` / `^from` / `^import` 追继承与依赖

### 产出结构

```
# 02 · 模块地图与继承关系

## 源码目录地图（目录树 + 职责）
## 核心继承关系（mermaid classDiagram，每条带 file:line 证据）
## 元类 / 装饰器 / 关键机制解析
## 跨包依赖（mermaid graph，按 import 推）
## 依赖版本约束（Python / Node 版本、特殊约束）
## 疑问清单进展
## 新发现（README 没强调的）
## 给阶段 3 的建议主线
```

### 关键要求

- 继承图里每个类必须能 grep 到真实定义位置
- mermaid 图必须语法正确（ class 名不含空格等）

## 阶段 3：追主线（产出 `03-main-flow.md`）

### 工具

- Grep 入口：`def main`、`__main__`、`def arun`、`def run`、CLI 入口
- Read 关键文件的**切片**：用 `offset + limit` 按需读，不盲读全文件
- Grep 函数定义位置，一步步跟踪调用链

### 产出结构

```
# 03 · 主线调用链

## 主线 A（最典型的路径）
   [ASCII 流程图，每步带 file:line]
## 主线 B（如有第二条代表性路径）
## 关键机制解析
   - 调度 / 参数合并 / 异常处理 / HITL 等
## 动态 / 并发 / 异步机制的实际运作
## 疑问清单进展
## 新发现（README 没说的）
## 给阶段 4 的建议
```

### 深度控制

- `quick`：只追 1 条主线（最核心入口）
- `standard`：追 2 条主线（含错误路径一瞥）
- `deep`：追 2-3 条主线 + 异常路径 + HITL/状态持久化路径

### 关键要求

- 每步 `file:line` 必须是 Grep/Read 能真实定位的
- 碰到大文件（> 500 行）先 Grep 定位，不盲读

## 阶段 4：挖设计决策（产出 `04-why.md`）

### 工具

- `git log --oneline -n 30` — 近期演进
- `git log --oneline --all --follow -- <file>` — 关键文件历史
- `git log --all -S "keyword"` — 搜功能引入点
- `git log --all --grep="..."` — 按 commit message 关键字搜
- `git show --no-patch --format="=== %h ===%n%s%n%n%b" <hash>` — 读完整 commit message

### 产出结构

```
# 04 · 设计决策与演进

## 架构演进时间线（按 PR / 关键 commit）
## N 条关键设计决策的「为什么」
   每条：
   - 决策（代码位置）
   - commit hash + message 原文
   - 推断动机
   - 代价 / 好处
## 命名演进 / 重构历史
## 代码里隐含的使用约束（docs 不警告的坑）
## 疑问清单最终状态（全部解答）
## 独立学习的最终小结（交给阶段 5 对比）
```

### 关键要求

- 每条「为什么」必须有 commit hash 佐证，或明确标「推断（基于：...）」
- **不编造作者意图** — 只报告 commit message 原文 + 合理推断

### 跳过条件

项目没有 git 历史（如压缩包下载）→ 跳过本阶段，或只做「从代码反推约束」部分

## 阶段 5：对比 docs（产出 `05-gap.md`）

这是**质量校验环节**，价值极高，不要省略。

### 工具

- Glob 项目内文档：`docs/**/*.md`、`docs/**/*.ipynb`
- Read 关键人工总结（通常是 `understanding/` / `getting-started/` / `concepts/` 目录下）
- 对比每个独立结论，在 docs 里找对应位置

### 产出结构

```
# 05 · 独立结论 vs 官方 docs 的 Gap 分析

## 总览表（维度 / 独立结论覆盖率 / 与 docs 冲突数）
## Part 1: 完全一致的核心结论（表格：我的位置 / docs 位置）
## Part 2: 独立工作比 docs 深的地方
## Part 3: docs 有、我缺失的（应用场景、命名典故、官方归纳）
## Part 4: 差异 / 冲突（如有）
## Part 5: 对独立工作方法的反思
## Part 6: 整体判定（准确性 / 深度 / 广度 / 可信度）
```

### 关键要求

- 对比必须具体到文件+行号，不笼统说「基本一致」
- 发现冲突时不要草率裁决「我对 docs 错」或反之，先分析差异根源（视角差异 / 一方遗漏 / 真冲突）

## 阶段 6：可选 — 给出适配建议

仅在阶段 0 用户提供了具体适配目标时执行。

基于前 5 份文档，给出：
- 需要改的文件清单（带 file:line）
- 影响范围估计
- 风险点（结合 04-why 里挖到的使用约束）

## 技术栈适配

不同语言的入口文件和依赖声明略有差异：

| 语言 | 依赖文件 | 典型入口 | 公开 API 位置 |
|---|---|---|---|
| Python | `pyproject.toml` / `setup.py` | `__main__.py` / `cli.py` / `main.py` | `__init__.py` |
| Node/TS | `package.json` / `tsconfig.json` | `src/index.*` / `main.ts` | `"main"` / `"exports"` 字段 |
| Go | `go.mod` | `cmd/*/main.go` | `internal/` vs `pkg/` |
| Rust | `Cargo.toml` | `src/main.rs` / `src/lib.rs` | workspace 用 `[workspace]` |
| Java/Kotlin | `pom.xml` / `build.gradle` | `Main.{java,kt}` | 按包名 |

适配时只改「找入口 + 读依赖」的具体命令，其他流程不变。

## 红线（必须遵守）

1. **不编造 `file:line`** — 所有引用用工具读出来的真实位置
2. **不把 README/docs 宣称当事实** — 先标「宣称」「待验证」，代码验证后再转「已验证」
3. **不在阶段 1-4 读项目 `docs/` 下的人工总结** — 防止污染独立结论
4. **不省阶段 5** — 这是质量校验环节
5. **不产出"通读报告"** — 学习要带着具体问题或目标

## 边界情况

- **项目太大**：阶段 2 只画核心 1-2 个子包的继承图，其他简述；阶段 3 按 `quick` 只追 1 条主线
- **没有 git log**：跳过阶段 4 或缩水到「从代码反推的约束」
- **没有 docs**：阶段 5 改做「自我校验」—— 回头检查 01-04 内部一致性
- **单文件项目**：阶段 1-3 合并成一份文档
- **用户已有初步印象**：阶段 0 问清他的「当前理解」，阶段 5 把他的理解也纳入对比对象

## 沟通风格

- 每阶段结束简短告知：文件路径 + 3-5 条关键发现 + 疑问进展
- 不把整份 md 内容复读到对话里，只给摘要
- 询问是否继续下一阶段（用户可能想调整方向）

## 工作参考实例

本 skill 的所有流程细节都在 `bridgic` 项目上实战验证过，可参考 `E:\github\bridgic\.learn-by-claude\` 下的 5 份 md 作为产出质量基线。
