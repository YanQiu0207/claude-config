---
name: workflow-test-generation
description: 测试生成。基于 spec.md 或被测代码，生成单元测试、集成测试、性能测试。当用户请求生成测试、TDD 模式触发；也由 workflow-code-generation 在每个 task 执行流程内嵌调用（owner/implementer 写测试，无人值守）。
---

> 输出一行：`Using workflow-test-generation`

# 测试生成

## Step 0: 意图识别与路径路由

根据调用上下文判断走哪条路径：

| 信号 | 路径 | 执行步骤 |
|------|------|---------|
| 由 `workflow-code-generation` 的 owner/implementer 在 task 内**内嵌调用**（无人值守） | **内嵌路径** | Step 2 → 3 → 4；**跳过 Step 1.5**（遇到前端 UI 场景自动降级为单元/集成测试并记录原因）**、跳过 Step 3 用户确认、跳过 Step 5**（测试通过后交还 owner 自跑 review） |
| 用户明确提到完整需求管理链接 | **完整流程** | Step 1 → 2 → 3 → 4 → 5 |
| 用户直接说"给 X 写个测试"/"补个单测"，指定了具体代码 | **快速补测试** | Step 2 → 3 → 4 |
| 由 `workflow-system-design` 讨论测试计划章节时加载 | **测试策略设计** | Step 1 → 2 → 3，只输出计划，不生成代码 |

> 如果无法判断，默认走**完整流程**。

---

## Step 1: 收集测试上下文

> **完整流程**和**测试策略设计**执行本步骤。**快速补测试**跳过（用户已指定了被测代码）。

尝试读取 `docs/design-docs/<module>/<feature>/spec.md`：

**有 spec.md**：
1. 读取 "7. 测试计划"
2. 测试计划明确 → 进入 Step 2
3. 测试计划不完整 → 补充读取 "2. 目标"、"3. 需求"、"4. 设计方案"，自行判断

**无 spec.md**（为已有代码补测试）：
- 询问用户要测哪些函数/类，基于代码生成

## Step 1.5: 前置条件检查（仅 E2E）

如果代码涉及前端 UI 流程（`.tsx` 文件或 spec.md 有用户操作路径），检查 E2E 前置条件：

```
检测到前端 UI 场景，E2E 测试需要 Playwright。
请确认：
- 已安装：npx playwright --version
- 已下载浏览器：npx playwright install chromium
```

未安装时告知用户命令，等待确认后继续；若用户跳过则只生成单元 / 集成测试，记录「E2E 未生成，原因：未安装 Playwright」。

---

## Step 2: 确定测试类型

根据代码特征自动判断需要哪些测试类型（**可组合，非互斥**；一个 feature 常组合多种），无法判断时才询问：

| 特征 | 测试类型 |
|------|----------|
| 纯函数、无外部依赖 | 单元测试 |
| 端到端流程、多组件交互 | 集成测试 |
| spec.md 有性能指标要求 | 性能测试 |
| 前端 UI 核心用户流程（.tsx 文件 / spec 有操作路径） | E2E 测试（Playwright） |

## Step 3: 制定测试计划

分析被测代码，制定测试计划（不生成代码）：

1. 读取被测代码，识别公共接口、输入/输出、副作用、需要 mock 的依赖
2. 读取 [reference/boundary-checklist.md](reference/boundary-checklist.md)，选择适用的边界条件
3. 根据项目需要，读取对应模块的测试参考文档（如有）
4. 为每个测试目标列出：正常路径、边界条件、异常场景的具体测试点

创建测试任务清单，**与用户确认**后再继续（内嵌路径除外，见 Step 0）：

```
示例：
1. [pending] UnitTest - FooClass::Bar() 正常路径 + 边界条件
2. [pending] UnitTest - FooClass::Bar() 异常处理
3. [pending] IntegrationTest - 端到端流程
```

> **测试策略设计路径**到此结束。将测试计划输出为 spec.md 测试计划章节的内容，不进入 Step 4。

## Step 4: 逐个生成测试

> 仅**完整流程**和**快速补测试**执行本步骤。

### 4.1 加载编码规范（🚨 强制前置）

| 规范 | 何时加载 |
|------|----------|
| `bp-coding-best-practices` | 始终 |
| `std-cpp` | `.cc`/`.cpp`/`.h` 文件 |
| `std-go` | `.go` 文件 |
| `std-python` | `.py` 文件 |

根据项目需要，额外加载其他编码规范 skill。

### 4.2 逐个生成

对每个测试任务生成测试代码。每个测试必须覆盖三类场景：
1. **正常路径** — happy path
2. **边界条件** — 基于 Step 3 选出的 boundary-checklist 条目
3. **异常场景** — 错误输入、异常处理

生成后更新构建配置，复用项目现有的测试基类和断言工具（不要自己造）。

#### E2E 测试（Playwright）专属规则

仅当 Step 2 判定需要 E2E 测试时执行：

- 加载 `frontend-playwright-verification` 获取浏览器 / Playwright 使用规范（定位器、等待、避免 sleep 等）
- 文件命名：`<feature>.e2e.ts`，放在对应 feature 目录内
- 每个 E2E 场景必须包含：
  - **正常流程**：完整用户操作路径（点击 → 填表 → 提交 → 验证结果）
  - **错误状态**：空表单提交、网络错误、无权限等
  - **边界状态**：空列表、超长输入、多页分页等
- 使用 `page.getByRole` / `page.getByText` 等语义选择器，禁止 CSS 选择器
- 网络拦截：用 `page.route()` mock API 响应，不依赖真实后端
- 断言必须用 `expect(locator).toBeVisible()` 等 Playwright 断言（自动等待，不要 `sleep`）

```ts
// 示例结构
import { test, expect } from '@playwright/test'

test.describe('UserList', () => {
  test('正常加载并显示用户列表', async ({ page }) => {
    await page.route('/api/users', route =>
      route.fulfill({ json: [{ id: '1', name: '张三' }] })
    )
    await page.goto('/users')
    await expect(page.getByRole('listitem')).toHaveCount(1)
    await expect(page.getByText('张三')).toBeVisible()
  })

  test('空列表显示引导操作', async ({ page }) => {
    await page.route('/api/users', route => route.fulfill({ json: [] }))
    await page.goto('/users')
    await expect(page.getByText('暂无用户')).toBeVisible()
    await expect(page.getByRole('link', { name: '添加用户' })).toBeVisible()
  })
})
```

每完成一个任务，标记 `[completed]`，继续下一个。

## Step 5: 收尾流程

> 仅**完整流程**执行本步骤（其余路径见 Step 0 路由表）。**前置条件**：所有测试用例已通过。

提示用户进入 `workflow-code-review` 进行 AI 代码评审（同时评审功能代码和测试代码）：
```
自测已全部通过。

推荐下一步：
- 说"CR"或"代码评审"进入 AI 代码评审阶段
```

---

## 强制规则

1. **测试计划必须经用户确认后才能生成代码**（内嵌路径除外，见 Step 0）
2. **必须覆盖三类场景**：正常路径 + 边界条件 + 异常场景
3. **必须应用 boundary-checklist**：Step 3 中读取并选择适用条目
4. **必须可编译运行**：包含所有必要头文件/导入，更新构建配置
5. **复用现有基础设施**：使用项目的测试基类和断言工具，不要自己造
6. **测试全部通过才能推进**：编译失败或用例未通过时，先修复，确认全部 PASS 后才可进入 CR
