---
name: std-react
description: React / Next.js / TypeScript / shadcn/ui 前端编码规范。写 .tsx/.ts 前端文件、实现 UI、重构组件、接入 shadcn/ui 或检查 React 性能时使用。基于 OpenAI build-web-apps 中 react-best-practices 与 shadcn-best-practices 的中文化本地版本，并保留本框架实现接线。
---

> 输出一行：`Using std-react`

# React + shadcn/ui 编码规范

## 默认技术栈

- 新复杂前端应用：React + Vite + TypeScript。
- 既有项目：遵守项目已有框架、路由、状态管理、组件库和包管理器。
- UI 基础组件：优先 shadcn/ui；不要手写已有基础组件。

## React / Next.js 性能规则

优先级从高到低：

1. **消除瀑布**：独立请求并行；需要时用 Suspense；不要在不需要的分支提前 `await`。
2. **控制包体**：避免 barrel imports；重组件动态加载；第三方脚本延后加载。
3. **服务端性能**：减少 RSC props 序列化；静态 I/O 提到模块级；服务端 action 需要鉴权。
4. **客户端数据**：服务端状态用 SWR / TanStack Query；不要 `useEffect` 里手搓 fetch 流程。
5. **减少重渲染**：派生状态直接在 render 中计算；回调用函数式 setState；不要在组件内定义子组件。
6. **渲染性能**：长列表用虚拟化或 `content-visibility`；静态 JSX 可提到组件外。
7. **JS 性能**：循环里避免重复正则、排序、属性读取；频繁查找用 Map / Set。

不要预防性 `memo`。先有性能证据，再优化。

## TypeScript 规则

- 开启 `strict`。
- Props 必须显式声明。
- 禁止 `any`；用 `unknown` + type guard。
- API 响应要校验；不要直接 `as ResponseType`。
- 联合常量用 `as const`；默认不用 `enum`。

## 组件结构

- 一个文件只放一个主组件。
- 组件名和文件名用 PascalCase。
- `App` 只做组合，不写成巨型组件。
- 重复 UI 抽成组件或 variant，不复制 className。
- 列表 `key` 必须是稳定 ID。
- 交互控件必须有 loading / disabled / error / empty 状态。

## shadcn/ui 规则

先看项目是否已有 `components.json`。使用项目包管理器运行 shadcn CLI，例如：

```bash
npx shadcn@latest info
npx shadcn@latest add button card dialog
npx shadcn@latest docs button dialog
```

规则：

1. 先查已有组件，再新增。
2. 使用组件内建 variant；不要用 raw color 覆盖。
3. 使用语义颜色：`bg-background`、`text-muted-foreground`、`bg-primary`。
4. 布局间距用 `gap-*`，不要用 `space-x-*` / `space-y-*`。
5. 等宽高用 `size-*`。
6. 条件 class 用 `cn()`。
7. Dialog / Sheet / Drawer 必须有 Title；可用 `sr-only` 隐藏。
8. Card 使用完整结构：`CardHeader` / `CardTitle` / `CardContent` / `CardFooter`。
9. Empty / Skeleton / Alert / Badge / Separator 优先用 shadcn 组件。
10. Button loading 用 `disabled` + Spinner 组合，不发明 `isLoading` prop。

## 常用组件选择

| 需求 | 组件 |
| --- | --- |
| 操作 | `Button` |
| 表单 | `Input` / `Select` / `Checkbox` / `RadioGroup` / `Textarea` |
| 数据展示 | `Table` / `Card` / `Badge` / `Avatar` |
| 导航 | `Sidebar` / `NavigationMenu` / `Breadcrumb` / `Tabs` |
| 弹层 | `Dialog` / `Sheet` / `Drawer` / `AlertDialog` |
| 反馈 | `sonner` / `Alert` / `Progress` / `Skeleton` / `Spinner` |
| 空态 | `Empty` |
| 图表 | shadcn `Chart` / Recharts |

## 禁止事项

| 禁止 | 替代 |
| --- | --- |
| `any` | 明确类型或 `unknown` |
| 组件内定义子组件 | 提到文件顶层 |
| `useEffect` 获取服务端数据 | SWR / TanStack Query |
| 手写 shadcn 已有组件 | `shadcn add` |
| raw Tailwind 颜色覆盖组件 | 语义 token |
| 表格概念改成卡片网格 | 保留 `ui-spec.md` 的信息结构 |
| 通过静态截图伪装 UI | 真实 code-native UI |

## 接线

实现前必须读 `spec.md` 和 `ui-spec.md`。实现后加载：

1. `bp-frontend-taste`
2. `frontend-playwright-verification`

## 参考来源

- OpenAI `react-best-practices`：<https://github.com/openai/plugins/tree/main/plugins/build-web-apps>
- OpenAI `shadcn-best-practices`：<https://github.com/openai/plugins/tree/main/plugins/build-web-apps>
