---
name: project-knowledge
description: 项目知识沉淀规范。定义项目文档的目录结构、spec 生命周期与归档约定、架构文档维护方式。当需要创建新文档或询问「某类文档放哪里」时参考此 skill。
---

> 输出一行：`Using project-knowledge`

# 项目知识沉淀规范

## 加载时机

- 创建或更新 `docs/design-docs/**/spec.md`、`tasks.md` 时加载
- 功能交付、任务完成、准备归档 spec 时加载
- 改动涉及新模块、接口变更、架构变更或重大技术选型时加载
- 用户询问项目架构、ADR、spec 归档或文档应放在哪里时加载
- 新需求立项、或需要了解项目历史任务时加载（看 `TASKBOARD.md`）
- 改代码需要定位功能落点 / 影响链路时加载（看 `dev-map.md`）

## 目录结构约定

```
docs/
├── architecture/                    # 项目级架构文档（常青）
│   ├── overview.md                  # 系统全貌（必须有）
│   ├── dev-map.md                   # 开发导航：功能落点与影响链路（推荐）
│   └── <subsystem>.md               # 子系统专项（按需）
├── adr/                             # 架构决策记录（可选，推荐）
│   └── NNN-<title>.md               # 例：001-choose-message-queue.md
└── design-docs/                     # Feature Spec（按功能创建）
    ├── TASKBOARD.md                 # 跨 feature 任务总览（项目级，单文件）
    └── <module>/
        └── <feature>/
            ├── spec.md              # 需求 + 设计文档
            └── tasks.md             # 任务拆分与进度
```

---

## 各类文档的定位与职责

### Feature Spec（`docs/design-docs/`）

每个功能或较大改动对应一个子目录，生命周期跟随功能：

```
Draft → In Review → Approved → Archived
Quick Draft → Approved → Archived
```

- **Spec**：记录「为什么做、做什么、怎么做」，在功能开发期间持续更新
- **Tasks**：记录「分几步做，每步的完成条件是什么」，在开发过程中实时更新
- **归档**：功能交付后将 spec.md 头部的 `状态` 字段改为 `Archived`，**文件原地保留，不移动**
  - 原地保留的好处：避免因移动文件导致已有引用失效

### 架构文档（`docs/architecture/`）

**常青文档（Evergreen Docs）**——始终反映系统当前状态：

- `overview.md`：系统全貌，1-2 页内，可在 10 分钟内读完
  - 内容：系统边界、核心模块、数据流、主要技术栈
  - 不记录「当初为什么这么选」——这属于 ADR
- `dev-map.md`：**开发导航地图**——偏代码落点，回答「改这个功能该动哪些文件」
  - 内容：功能 → 落点文件、配置定义位置、模块改动的影响链路、项目既有写法 / 惯例
  - 与 `overview.md` 的分工：overview 偏架构全貌（是什么），dev-map 偏代码落点（在哪改）
  - 维护：**谁动代码谁更新**——`workflow-code-generation` 改码前先查、落点变化后回写
  - 仓库大时可按子系统拆成多份，每份封面写清管哪一片
- `<subsystem>.md`：各子系统的设计细节（按需创建）

**维护时机**：每当一个功能 spec 的状态变为 `Approved` 且涉及架构变更时，必须同步更新 `architecture/`。

### 架构决策记录（`docs/adr/`）

记录**不可逆或高影响的架构决策**，一旦写定不修改（只更新状态字段）：

```markdown
# NNN: <决策标题>

**状态**: Accepted / Superseded by NNN

## 背景
<!-- 当时面临什么问题，为什么需要做这个决定 -->

## 决策
<!-- 我们选择了什么方案 -->

## 后果
<!-- 这个决定带来了什么，有什么已知的权衡 -->
```

**何时写 ADR**：
- 引入新的存储系统或消息队列
- 放弃某个技术方向
- 确立团队编码约定
- 选择某个有显著权衡的架构模式

---

## 跨 feature 任务看板（`docs/design-docs/TASKBOARD.md`）

项目级的任务总览（单文件），让新需求进来时能一眼看到历史，避免「新需求把旧设计冲掉」、重复造轮子。

- **记什么**：每个 feature 的名称、状态（对齐 spec 生命周期）、当前阶段、spec 目录、一句话交付结论
- **谁维护**：
  - `workflow-requirements-clarification` 澄清**前先读** TASKBOARD，判断是否旧需求延续、有无类似历史
  - `workflow-code-generation` 任务完成 / spec 归档时，更新对应行
- **粒度**：一个 feature 一行；不替代各 feature 自己的 `tasks.md`（那是任务级，看板是 feature 级）

模板见 [reference/taskboard_template.md](reference/taskboard_template.md)。

---

## 文档与代码的同步原则

| 变更类型 | 需要更新的文档 |
|---------|--------------|
| 新需求立项 | 在 `design-docs/TASKBOARD.md` 新增一行 |
| 功能开发完成 | spec.md 状态改为 `Archived`；更新 `design-docs/TASKBOARD.md` 对应行 |
| 涉及新模块或接口变更 | `architecture/overview.md`（或对应子系统文档） |
| 功能落点 / 影响链路变化 | `architecture/dev-map.md` |
| 重大架构选型或方向调整 | 新建一条 ADR |
| 编码规范变更 | 对应 `std-*` skill 文件 |
| 工程流程变更 | 对应 `workflow-*` skill 文件 |

**文档债务**：如果代码已变更但文档尚未更新，在 tasks.md 中创建一个「更新文档」任务，不要跳过。

---

## 与其他工作流的关系

| 工作流 | 产出 | 在哪里 |
|-------|------|--------|
| `workflow-requirements-clarification` | spec.md（1-3 章） | `docs/design-docs/<module>/<feature>/spec.md` |
| `workflow-system-design` | spec.md（4-8 章） | 同上 |
| `workflow-quick-design` | spec.md（Quick Draft） | 同上 |
| `workflow-code-generation` | tasks.md + 代码 | `docs/design-docs/<module>/<feature>/tasks.md` |
| `self-refinement` | skill 文件更新 | `skills/` 目录下对应 skill |

架构文档（`docs/architecture/`）和 ADR（`docs/adr/`）默认不由设计工作流自动创建；当 `tasks.md` 判断存在文档同步需求时，应显式创建「更新项目知识文档」任务，并在代码任务完成前处理或保留为未完成任务。
