---
name: opsx-project-knowledge
description: OpenSpec 项目知识沉淀规范。定义 openspec 目录结构、变更生命周期与归档约定、架构文档维护方式。当需要创建新变更目录或询问「某类文档放哪里」时参考此 skill。
---

Using opsx-project-knowledge

# OpenSpec 项目知识沉淀规范

## 加载时机

- 创建或更新 `openspec/changes/*/` 下任意文件时加载
- 功能交付、任务完成、准备归档变更时加载
- 改动涉及新模块、接口变更、架构变更或重大技术选型时加载
- 用户询问项目架构、ADR、变更归档或文档应放在哪里时加载

## 目录结构约定

```
openspec/
├── changes/                         # 活跃变更（开发中）
│   └── <change-name>/               # 单次变更目录（动词-名词，如 add-dark-mode）
│       ├── .openspec.yaml           # 变更元数据（必选）
│       ├── proposal.md              # 为什么改、改什么（必选）
│       ├── tasks.md                 # 实现任务清单（必选）
│       ├── design.md                # 技术设计（可选，见触发条件）
│       └── specs/                   # 增量规范（必选）
│           └── [capability]/
│               └── spec.md          # ADDED / MODIFIED / REMOVED
└── changes/archive/                 # 已归档变更
    └── YYYY-MM-DD-<change-name>/    # 整目录归档，名称加日期前缀

docs/
├── architecture/                    # 项目级架构文档（常青）
│   ├── overview.md                  # 系统全貌（必须有）
│   └── <subsystem>.md               # 子系统专项（按需）
└── adr/                             # 架构决策记录（可选，推荐）
    └── NNN-<title>.md               # 例：001-choose-message-queue.md
```

---

## 各类文档的定位与职责

### 变更目录（`openspec/changes/<change-name>/`）

每次功能开发或较大改动对应一个变更目录，生命周期跟随变更：

```
Draft → In Review → Approved → Archived
Quick Draft → Approved → Archived
```

| 文件 | 职责 | 是否必选 |
|------|------|---------|
| `.openspec.yaml` | 变更元数据：名称、作者、日期、状态 | 必选 |
| `proposal.md` | 为什么改、改什么：背景、目标、需求概览、备选方案 | 必选 |
| `tasks.md` | 分几步做，每步的完成条件是什么 | 必选 |
| `design.md` | 怎么做：组件设计、核心逻辑、测试计划、可观测性 | 可选（见触发条件） |
| `specs/<capability>/spec.md` | 增量规范：该 capability 的规范变更内容 | 必选 |

#### design.md 触发条件

满足以下任一条件时需创建 `design.md`：

- 涉及新模块或子系统的设计
- 接口或数据模型有破坏性变更
- 核心逻辑存在算法复杂度或并发安全问题
- 需要明确测试计划或可观测性方案

简单的 bug 修复、配置调整、文案变更不需要 `design.md`。

#### 归档

执行 `/opsx-archive` 后，整个变更目录移动到 `openspec/changes/archive/`，并在目录名前加上归档日期：

```
openspec/changes/add-dark-mode/
    ↓ /opsx-archive
openspec/changes/archive/2026-06-17-add-dark-mode/
```

`.openspec.yaml` 的 `status` 字段同步更新为 `Archived`。

### 架构文档（`docs/architecture/`）

**常青文档（Evergreen Docs）**——始终反映系统当前状态：

- `overview.md`：系统全貌，1-2 页内，可在 10 分钟内读完
  - 内容：系统边界、核心模块、数据流、主要技术栈
  - 不记录「当初为什么这么选」——这属于 ADR
- `<subsystem>.md`：各子系统的设计细节（按需创建）

**维护时机**：每当一个变更的 `.openspec.yaml` 状态变为 `Approved` 且涉及架构变更时，必须同步更新 `architecture/`。

### 架构决策记录（`docs/adr/`）

记录**不可逆或高影响的架构决策**，一旦写定不修改（只更新状态字段）：

```markdown
# NNN: <决策标题>

**状态**: Accepted / Superseded by NNN

## 背景
## 决策
## 后果
```

**何时写 ADR**：引入新的存储系统或消息队列、放弃某个技术方向、确立团队编码约定、选择某个有显著权衡的架构模式。

---

## 文档与代码的同步原则

| 变更类型 | 需要更新的文档 |
|---------|--------------|
| 变更交付完成 | 执行 `/opsx-archive` 归档 |
| 涉及新模块或接口变更 | `architecture/overview.md`（或对应子系统文档） |
| 重大架构选型或方向调整 | 新建一条 ADR |
| 编码规范变更 | 对应 `std-*` skill 文件 |
| 工程流程变更 | 对应 `workflow-*` / `opsx-*` skill 文件 |

**文档债务**：如果代码已变更但文档尚未更新，在 `tasks.md` 中创建一个「更新文档」任务，不要跳过。

---

## 与其他工作流的关系

| 工作流 | 产出 | 路径 |
|-------|------|------|
| `opsx-requirements-clarification` | `.openspec.yaml` + `proposal.md` + `specs/*/spec.md` | `openspec/changes/<change-name>/` |
| `opsx-system-design` | `design.md` | 同上 |
| `opsx-quick-design` | `.openspec.yaml` + `proposal.md`（Quick Draft） | 同上 |
| `opsx-code-generation` | `tasks.md` + 代码 | 同上 |
| `opsx-archive` | 整目录移动 | `openspec/changes/archive/YYYY-MM-DD-<change-name>/` |
| `self-refinement` | skill 文件更新 | `skills/` 目录下对应 skill |

架构文档（`docs/architecture/`）和 ADR（`docs/adr/`）不由设计工作流自动创建；当 `tasks.md` 判断存在文档同步需求时，应显式创建「更新项目知识文档」任务。
