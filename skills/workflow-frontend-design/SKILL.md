---
name: workflow-frontend-design
description: 通用前端 UI 工作流入口。检测到新页面、复杂新组件、绿地 Web App、Dashboard、Landing Page、前端重设计或明显视觉改版时使用；复杂组件和小页面走轻量档，页面级 / Web App / 重设计走重型档；极轻 UI 调整或单文件小组件改动直接走 workflow-code-generation。基于 Anthropic frontend-design 与 OpenAI frontend-app-builder 的中文化本地版本：先做有观点的设计方向和完整概念，再沉淀 ui-spec.md，最后交给 workflow-code-generation 实现与浏览器验证。
---

> 输出一行：`Using workflow-frontend-design`

# 前端 UI 设计

## 官方规则本地化

### 设计负责人视角

把自己当成小型设计工作室的设计负责人。用户不是要模板，而是要一个清晰、独特、能解释的视觉观点。

必须做：

- 明确产品主题、受众和页面唯一任务。
- 从产品自身世界提取视觉语言：材料、工具、场景、行业物件、用户习惯。
- 对色彩、字体、布局做明确选择，并说明原因。
- 至少承担一个可解释的审美风险。

避免：

- 默认紫色渐变、统一大圆角、泛用 Bento、过多居中布局。
- 无意义 eyebrow / kicker / badge / pill。
- 假指标、假标签、装饰性图标堆叠。
- 只做 Hero，不做完整页面。

### 概念先于实现

实现前必须先产出设计概念。概念一旦被用户接受，就视为生产规格。

规则：

1. 先设计完整请求面：页面、状态、核心流程和响应式延展。
2. 多 section 页面按 section 保持节奏，不要用一张模糊长图或一个压缩概念糊弄。
3. 接受后的概念不能随意改文案、层级、容器模型、色彩、字体、密度和 section 顺序。
4. 编码前抽取设计系统：tokens、字体、组件族、间距、图标、容器、动效。
5. 新复杂应用默认 React + Vite；既有项目遵循项目技术栈。
6. 完成标准是浏览器实现与接受概念高度一致；有明显设计评审意见就继续修。

## 本框架接线

本 skill 不探测 Claude Code / Codex 外部技能。官方能力已本地化到本目录。

## 分档规则

- **轻量档**：复杂组件、小页面、局部页面重排。只出 1 个 HTML 方案；用户确认后生成精简 `ui-spec.md`，作为实现契约。
- **重型档**：页面级功能、Web App、Dashboard、Landing Page、重设计。出 2-3 个 HTML 方案；用户确认后生成完整 `ui-spec.md`。
- 不确定时按重型档处理；用户明确要求快速推进时可降为轻量档。

闭环由本地 workflow 承担；官方技能能力拆到各阶段：

```text
workflow-frontend-design（定方向 / 出概念 / 产出 ui-spec）
  → bp-frontend-layout（页面骨架）
  → workflow-code-generation + std-react（实现 / 生成 tasks.md）
  → workflow-test-generation（tasks 中的测试任务）
  → bp-frontend-taste（视觉质检）
  → frontend-playwright-verification（最终浏览器验证）
  → 失败则回到实现修复
```

## 工作流程

### Step 1：读取 spec

确认 `docs/design-docs/<module>/<feature>/spec.md` 存在。不存在则停止：

```text
缺少 spec.md，无法提取 UI 需求。请先运行 /requirements-clarification 或 /quick-design 生成功能规格，再调用本工作流。
```

读取：

- 页面目标、用户、核心任务。
- 必须出现的 section、数据、状态、操作。
- 品牌、技术栈、组件库、响应式和验收约束。

只问会阻塞设计的问题；不要问「喜欢什么风格」。

### Step 2：按档位出 HTML 方案

先判断档位，再生成单文件 HTML：

- 路径：`docs/design-docs/<module>/<feature>/ui-mockup-A.html`。
- Tailwind CDN，可直接打开。
- 轻量档只生成 1 个方案。
- 重型档生成 2-3 个方案，方向必须明显不同，但业务事实一致。
- 必须包含正常态、空态、加载态、错误态。
- 必须体现桌面和移动端布局。

每个方案说明：

- 主题语境。
- 色彩与字体。
- 布局骨架。
- 组件语言。
- 视觉记忆点。

### Step 3：等用户选择

输出：

```text
已按 [轻量档 / 重型档] 生成 N 个 UI 方案，请在浏览器中打开对比：

- 方案 A（路径）：[一句话说明方向]
- 方案 B（路径）：[一句话说明方向]
- 方案 C（路径，如有）：[一句话说明方向]

请告知选择哪个方案，或需要融合哪些元素。
```

用户确认前不要写实现代码。

### Step 4：确定布局骨架并产出 ui-spec

用户选定方案后，先**加载 `bp-frontend-layout`**，确定页面类型、区域划分、主操作位置、容器模型、section 节奏和响应式塌缩，把结果写进下方模板的「布局骨架」section。轻量档可以压缩描述，但不得省略实现必需信息。

随后写入 `docs/design-docs/<module>/<feature>/ui-spec.md`，**每个 section 必须填实，不得只留空标题**：

```markdown
# UI 规格：<feature>

## 选定方案
[方案 X + 一句话方向]

## 页面唯一任务
[这个页面 / 组件要让用户完成的唯一任务]

## 设计方向
[主题语境、受众、承担的可解释审美风险]

## 设计 Tokens
[背景 / Surface / 文本 / 弱文本 / 边框 / 主色 / 语义色，给具体色值]

## 字体系统
[标题 / 正文 / 标签 / 控件文字的字体、字号、字重、行高层级]

## 布局骨架
[由 bp-frontend-layout 写入：页面类型、区域划分、主操作位置、容器模型、桌面布局、移动端布局]

## 组件清单
- [组件名]：[职责]

## 交互与状态
- hover / focus / active / disabled
- 空态：[描述]
- 加载态：[描述]
- 错误态：[描述 + 重试入口]

## 响应式
- 移动端（< 768px）：[布局说明]
- 桌面端（≥ 1024px）：[布局说明]

## 保真清单
[实现必须对齐的视觉要点，供 bp-frontend-taste 收尾质检对照]

## 浏览器验证点
[必须在浏览器验证的关键流程与渲染结果，供 frontend-playwright-verification 对照]
```

### Step 5：进入实现

输出：

```text
UI 规格已产出：docs/design-docs/<module>/<feature>/ui-spec.md
正在进入代码实现阶段，加载 workflow-code-generation。
tasks.md 必须包含实现任务、测试任务和最终浏览器验证任务。
```

## 强制规则

1. 不检测外部 CLI 技能。
2. 不跳过概念确认。
3. 不只做 Hero。
4. 不把接受后的概念重新解释一遍再实现。
5. 产出 ui-spec 前必须加载 `bp-frontend-layout` 写实「布局骨架」；ui-spec 各 section 不得留空标题。
6. 可见 UI 完成后必须走 `bp-frontend-taste` 和 `frontend-playwright-verification`。

## 参考来源

- Anthropic `frontend-design`：<https://github.com/anthropics/skills/tree/main/skills/frontend-design>
- OpenAI `build-web-apps / frontend-app-builder`：<https://github.com/openai/plugins/tree/main/plugins/build-web-apps>
