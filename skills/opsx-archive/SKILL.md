---
name: opsx-archive
description: OpenSpec 变更归档。将 openspec/changes/<change-name>/ 整目录移动到 openspec/changes/archive/YYYY-MM-DD-<change-name>/，并更新 .openspec.yaml 状态为 Archived。由 /opsx-archive 命令触发。
---

Using opsx-archive

# OpenSpec 变更归档

## 触发条件

- 用户执行 `/opsx-archive`
- 当前变更的代码已合入主干，或用户明确确认变更已完成

---

## 工作流程

### Step 1：确认变更目录

在 `openspec/changes/` 下列出所有活跃变更（排除 `archive/` 子目录），让用户选择要归档的变更：

```
当前活跃变更：
1. add-dark-mode（Draft，2026-06-10）
2. fix-auth-timeout（Approved，2026-06-15）

请问要归档哪个变更？
```

如果当前上下文已有明确的变更目录（如用户在该目录下工作），直接使用，无需询问。

### Step 2：确认归档

展示变更摘要，请用户确认：

```
即将归档：add-dark-mode

  状态：Approved
  作者：xxx
  日期：2026-06-10
  文件：proposal.md、design.md、tasks.md、specs/ui/spec.md

归档后目录将移动到：
  openspec/changes/archive/2026-06-17-add-dark-mode/

确认归档？（y/n）
```

### Step 3：执行归档

用户确认后：

1. **更新 `.openspec.yaml`**：将 `status` 字段改为 `Archived`，写入归档日期

   ```yaml
   status: Archived
   archived_date: YYYY-MM-DD
   ```

2. **移动目录**：

   ```bash
   mkdir -p openspec/changes/archive
   mv openspec/changes/<change-name> \
      openspec/changes/archive/$(date +%Y-%m-%d)-<change-name>
   ```

3. **检查文档同步**：读取 `.openspec.yaml` 和 `proposal.md`，判断是否需要更新架构文档或写 ADR：
   - 涉及新模块或接口变更 → 提示更新 `docs/architecture/`
   - 涉及重大架构决策 → 提示新建 `docs/adr/`
   - 否则 → 无需额外操作

### Step 4：输出归档报告

```
✅ 归档完成

  变更：add-dark-mode
  归档路径：openspec/changes/archive/2026-06-17-add-dark-mode/

  📋 文档同步提醒：
  - [涉及 UI 模块变更] 建议更新 docs/architecture/overview.md
```

---

## 强制规则

1. **必须用户确认后才执行移动**：不得静默归档
2. **移动前更新 `.openspec.yaml`**：确保归档状态写入文件后再移动目录
3. **只归档 `openspec/changes/` 下的目录**：不操作其他路径
4. **归档目录名格式**：`YYYY-MM-DD-<change-name>`，日期为执行归档当天
