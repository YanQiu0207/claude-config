---
name: opsx-system-design
description: OpenSpec 系统设计。当 proposal.md 已完整但 design.md 不存在或为空时调用。按 design.md 章节顺序逐个与用户讨论，每轮只处理一个 section。
---

> 输出一行：`Using opsx-system-design`

# OpenSpec 系统设计

## 核心定位

**AI 负责调研代码背景，用户主导设计决策。**

### AI 职责划分

| AI 自己调研（读代码） | 与用户讨论 |
|----------------------|-----------|
| 现有模块结构和职责 | 设计方向和权衡取舍 |
| 已有接口和数据结构 | 接口变更决策 |
| 依赖关系和调用链 | 模块划分决策 |
| 技术约束（框架、协议） | 性能/可维护性权衡 |

**规则**：如果信息可以从 codebase 获取，**AI 必须自己调研**，不问用户。

### 何时生成 design.md

| 场景 | 是否生成 |
|------|---------|
| 涉及新模块或子系统设计 | 是 |
| 接口或数据模型有破坏性变更 | 是 |
| 核心逻辑存在算法复杂度或并发安全问题 | 是 |
| 需要明确测试计划或可观测性方案 | 是 |
| 简单 bug 修复、配置调整、文案变更 | 否 |

如果判断不需要 `design.md`，告知用户并直接建议进入 `opsx-code-generation`。

## 前置条件

- `proposal.md` 已存在且内容完整（背景、目标、需求概览）
- 如果不存在或不完整 → **停止，切换到 `opsx-requirements-clarification` Skill**

## 触发条件

- 用户说「开始设计」、「设计方案」
- `opsx-requirements-clarification` 完成后用户确认进入设计阶段

---

## 规范加载（按需）

**在讨论到相关 section 时才加载对应规范**，不要在开始时一次性加载：

| 规范 | 何时加载 |
|------|----------|
| `bp-architecture-design` Skill | 讨论 1.1 方案概览时加载 |
| `bp-component-design` Skill | 讨论 1.2 组件设计时加载 |
| `bp-distributed-systems` Skill | 涉及网络通信、多节点协调、数据一致性、故障恢复时加载 |
| `bp-performance-optimization` Skill | 1.3 核心逻辑完成后加载 |
| `opsx-test-generation` Skill | 讨论 2. 测试计划时加载 |

---

## 工作流程

### Step 0：代码调研 + 需求摘要（AI 自主完成）

**目标**：理解现有实现 + 确认对需求的理解。

**AI 操作**：
1. 读取 `proposal.md`（背景、目标、需求概览）和所有 `specs/*/spec.md`
2. 调用 `codebase-researcher` subagent 深度调研相关代码
3. 生成摘要向用户确认

**向用户汇报（必须）**：

```
我已读完 proposal.md 并调研了相关代码：

**需求理解**：
- 问题：[复述 proposal.md 中的问题]
- 目标：[复述目标]
- 关键约束：[复述非功能需求]

**代码调研**：
- 相关模块：[列出发现的模块]
- 现有接口：[列出相关接口]
- 技术约束：[发现的约束]

请确认我的理解是否正确？有遗漏或错误的地方吗？
```

**结束条件**：用户确认理解正确。**必须等用户确认后才能进入设计讨论**。

### Step 1：初始化 design.md

确认需要 `design.md` 后，复制模板：

```bash
cp skills/opsx-system-design/reference/design_template.md \
   openspec/changes/<change-name>/design.md
```

填写文件头部的变更名称、作者、日期字段。

### Step 2：开始设计讨论

```
好的，我们现在进入**系统设计**阶段，从 **1.1 方案概览**开始。

请描述一下你的整体设计思路。
```

### Step 3：按 section 顺序讨论

**每轮只讨论一个 section**。详细的 section 引导模式参见 [reference/section-guide.md](reference/section-guide.md)。

**判断 section 是否适用**：

```
AI：「1.2.3 数据模型这个 section，你的需求涉及新的数据结构吗？不涉及可以跳过。」
```

用户跳过时，在 `design.md` 标注 `N/A - 本需求不适用`。

### Step 4：更新 design.md

每个 section 完成后：
1. 复述用户设计内容，确认理解正确
2. 将**用户确认的内容**写入 `design.md`
3. 进入下一个 section

---

## 强制规则

1. **AI 自主调研代码**：现有实现、接口等信息 AI 必须自己读代码获取
2. **设计前先确认理解**：展示需求摘要 + 代码调研结果，等用户确认
3. **默认用户主导**：AI 默认只提问和质疑
4. **用户请求时可生成**：用户明确请求帮助时，AI 可以生成设计建议
5. **生成前必须追问**：即使用户请求帮助，也要先追问确认约束和目标
6. **每轮一个 section**：按顺序逐个讨论
7. **严格顺序约束**：1.1 未完成前禁止讨论或写入 1.2/1.3
8. **只记录确认内容**：`design.md` 内容必须是用户确认的

## 反模式

| ❌ 错误做法 | ✅ 正确做法 |
|------------|-----------|
| 问用户「现有实现是怎样的」 | AI 自己读代码调研 |
| 直接开始设计讨论 | 先展示需求摘要 + 代码调研，确认后再开始 |
| 用户没请求就给方案 | 先提问，等用户请求帮助再给建议 |
| 生成设计后当作最终方案 | 询问「你倾向于哪个方向？」 |
| 1.1 讨论中写入具体函数签名 | 记录备忘，进入 1.2 时再写入 |

---

## 设计完成后

```
design.md 已完成：openspec/changes/<change-name>/design.md

你可以：
- 说「开始编码」进入 code generation 阶段
- 说「先写测试」进入 TDD 模式
- 如果某个 section 需要修改，告诉我具体哪个
```

## 参考资料

- [Section 引导指南](reference/section-guide.md)
- [Design 模板](reference/design_template.md)
