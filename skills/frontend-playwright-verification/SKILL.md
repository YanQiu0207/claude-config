---
name: frontend-playwright-verification
description: 前端效果最终验证门。前端/UI 改动后使用浏览器或 Playwright 验证页面身份、控制台、DOM、截图、交互、响应式和 ui-spec 保真度。基于 Anthropic webapp-testing 与 OpenAI frontend-testing-debugging 的中文化本地版本。
---

> 输出一行：`Using frontend-playwright-verification`

# 前端浏览器验证

## 核心规则

必须验证**运行中的页面**。源码检查、构建通过、单测通过，都不能替代浏览器验证。

优先顺序：

1. 可用内置 Browser / IAB 时先用它。
2. 不可用时优先用 `playwright-mcp-parallel` MCP，以便创建多个隔离浏览器实例并行验证。
3. 项目已有 Playwright E2E 时，复用项目脚本。
4. 若都不可用，说明阻塞和未验证风险。

## 先定义被测流程

验证前写一句：

```text
被测流程：[入口路由] -> [用户动作或状态] -> [预期渲染结果]
```

一般 smoke test 可写：

```text
被测流程：应用加载 -> 首个有意义页面渲染 -> 主要可见控件无运行时错误。
```

## 验证步骤

1. 找到目标 URL。若不清楚，先查项目脚本、端口和路由。
2. 启动或复用开发服务器。
3. 打开页面。
4. 检查页面身份：URL、title、关键文案。
5. 检查不是空白页。
6. 检查没有 Next.js / Vite / Webpack 错误遮罩。
7. 检查 console error / warn；相关错误必须解释或修复。
8. 执行目标交互：点击、输入、切换、筛选、打开弹窗、提交。
9. 用 DOM 证明状态正确。
10. 截图检查视觉：桌面至少一张；涉及响应式时加移动端。
11. 对照 `ui-spec.md` 或接受概念，记录偏差并修复。
12. 修复后重复验证。

## DOM 与截图分工

- DOM 证明：元素存在、文案正确、按钮状态、弹窗开关、表单值、URL、列表行、错误态。
- 截图证明：布局、间距、遮挡、溢出、颜色、字体、响应式、整体成熟度。

不要只用 DOM 声称视觉正确。不要只用截图声称流程可用。

## Playwright MCP fallback

无内置 Browser 时：

1. 查 MCP 工具列表，优先使用 `playwright-mcp-parallel` 暴露的 `instance_*` 和 `page_*` 工具。
2. 查 `package.json`，用项目包管理器启动应用。
3. 创建独立实例：`instance_create`。
4. 用 `page_browser_navigate`、`page_browser_snapshot`、`page_browser_click`、`page_browser_screenshot` 等工具完成验证。
5. 需要并行验证多条流程或多视口时，为每条流程创建独立 `instanceId`。
6. 项目已有 e2e 时，优先跑项目 e2e。
7. 没有 MCP 且没有 e2e 时，才用临时 Playwright 脚本打开 URL、收集 console、截图、跑目标交互。
8. 临时脚本、截图、trace 默认放临时目录；不要写进 repo，除非用户要求。

不要未经允许安装新浏览器依赖。

## 保真检查

可见 UI 改动必须检查：

- 文案、导航、CTA、section 顺序。
- 首屏重心和下一 section 露出。
- 色彩、渐变、字体、字重、行高。
- 间距、圆角、边框、阴影、容器模型。
- 图片裁切、图标风格、背景融合。
- 桌面和移动端。
- 核心交互是否更新真实 UI 状态。

若任一项会被设计评审指出，继续修。

## 交付格式

最终回复包含：

- 验证 URL 和视口。
- 被测流程。
- 浏览器方式：Browser / Playwright / 阻塞原因。
- DOM 检查结果。
- 截图路径或截图说明。
- console 错误结论。
- 修复过的视觉 / 交互问题。
- 未验证风险。

## 参考来源

- Anthropic `webapp-testing`：<https://github.com/anthropics/skills/tree/main/skills/webapp-testing>
- OpenAI `frontend-testing-debugging`：<https://github.com/openai/plugins/tree/main/plugins/build-web-apps>
