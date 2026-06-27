---
name: bp-frontend-taste
description: 前端视觉质量收尾质检。React/shadcn UI 实现后、浏览器验证前使用。基于 Anthropic frontend-design 与 OpenAI frontend-app-builder 的中文化本地规则，检查实现是否像一个成熟设计团队交付，而不是模板化 AI 页面。
---

> 输出一行：`Using bp-frontend-taste`

# 前端视觉质量基准

## 核心标准

页面要「清晰、克制、有观点」。不要像默认模板。

检查顺序：

1. 是否忠实执行 `ui-spec.md`。
2. 是否覆盖完整页面和状态。
3. 是否有清晰首屏、主任务和主操作。
4. 是否避免模板化痕迹。
5. 是否能通过浏览器截图评审。

## 必查项

### 布局

- 第一眼看到页面最重要的信息。
- 主操作一屏内可见。
- Section 节奏有变化，不重复同一种卡片公式。
- 宽屏不空散，移动端不横向溢出。
- 表格型信息不要强行改成卡片网格。

### 字体

- 标题、正文、标签、控件文字有明确层级。
- 不依赖浏览器默认按钮 / 输入框字体。
- 正文最小 14px，常规正文 16px。
- 行高、字重、字距一致。

### 色彩

- 背景、Surface、文本、弱文本、边框、主色、语义色来自 `ui-spec.md`。
- 不擅自把白色改成米色 / 暖灰。
- 不加未批准的渐变、发光、色罩。
- 文本对比度足够。

### 组件状态

必须有：

- Button：default / hover / active / disabled / loading。
- Input：default / focus / error / disabled。
- 数据区域：正常态 / 空态 / 加载态 / 错误态。
- 可点击元素：清晰 hover / focus。

### 图标与图片

- 图标隐喻、粗细、尺寸、颜色与设计一致。
- 不用泛用图标替换有意义的图标。
- 图片裁切、边缘、背景融合自然。
- 不用占位图、粗糙 SVG 或 CSS 图形冒充设计资产。

## 硬停止

看到以下问题，不能宣布完成：

- 首屏主要内容裁剪、重叠、意外换行。
- 移动端横向滚动。
- 文案、section 顺序、颜色、字体明显偏离 `ui-spec.md`。
- 新增未批准 eyebrow / badge / pill / 假指标。
- 控件看起来是浏览器默认样式。
- 空态、加载态、错误态缺失。
- 截图看起来像半成品或模板。

## 交付前一句话结论

最终汇报必须说明：

```text
已按 bp-frontend-taste 检查：布局、字体、色彩、状态、响应式和 ui-spec 保真度通过 / 存在以下问题。
```

## 参考来源

- Anthropic `frontend-design`：<https://github.com/anthropics/skills/tree/main/skills/frontend-design>
- OpenAI `frontend-app-builder`：<https://github.com/openai/plugins/tree/main/plugins/build-web-apps>
