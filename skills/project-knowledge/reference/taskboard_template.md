# 项目任务看板（TASKBOARD）

> 跨 feature 的任务总览（项目级）。一个 feature 一行：新需求立项时新增行，状态 / 阶段变化时更新；feature 交付后保留并标 `Archived`。
> 状态对齐 spec 生命周期：`Draft → In Review → Approved → Archived`（轻量流程：`Quick Draft → Approved → Archived`）。

| Feature | 状态 | 当前阶段 | Spec 目录 | 交付结论 |
|---------|------|---------|----------|---------|
| 示例：导出 CSV | In Review | 系统设计 | `design-docs/report/csv-export/` | — |
| 示例：登录限流 | Archived | 已交付 | `design-docs/auth/rate-limit/` | 滑动窗口限流，默认 100 req/min，可配置 |
