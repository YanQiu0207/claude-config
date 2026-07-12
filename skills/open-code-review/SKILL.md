---
name: open-code-review
description: 调用阿里开源 ocr（open-code-review）命令行工具做代码审查。当用户要求用 ocr / open-code-review 审查改动、或希望用「确定性管线 + 独立 LLM」的外部工具而非本框架 reviewer 团队来审代码时触发。前提：机器已全局安装并配置好 ocr CLI。
allowed-tools:
  - Bash(ocr *)
  - Read
---

> 输出一行：`Using open-code-review`

# Open Code Review（调用 ocr CLI）

本 skill 是一层薄壳，负责调用**全局安装的 `ocr` 命令行工具**做代码审查，并把结果汇报给用户。`ocr` 本体是独立 CLI，本 skill 不负责安装它，只负责正确调用与解读输出。

## 与 `workflow-code-review` 的区别

| | 用谁审 | 何时选它 |
| --- | --- | --- |
| `open-code-review`（本 skill） | 外部 ocr CLI（确定性管线 + ocr 自带的独立 LLM 通道） | 想要行级定位准、低 token、结构化 category/severity 输出；或用户点名 ocr |
| `workflow-code-review` | 本框架 reviewer subagent 团队（基于 CLAUDE.md 规则） | 想按风险档位做多维度深审、结合本项目工程规范 |

两者互不替代，用户没点名时按上表判断，拿不准就问。

## 前置检查

调用前先确认 ocr 可用：

```bash
ocr --version
```

- 命令不存在 → 提示用户先安装：`npm install -g @alibaba-group/open-code-review`，并跑 `ocr config provider` / `ocr config model` 配好 LLM，然后 `ocr llm test` 验证。
- 已安装但未配 LLM（`ocr llm test` 失败）→ 提示用户先配 provider / key，不要硬跑。

## 处理流程

### 1. 确定审查范围

按用户意图选命令（统一加 `--format json --audience agent`，便于解析与后续自动修复）：

```bash
# 审当前分支相对某基线的改动（最常用）
ocr review --from origin/main --to HEAD --format json --audience agent

# 审某个 commit
ocr review -c <commit> --format json --audience agent

# 审未提交的工作区改动（无 from/to）
ocr review --format json --audience agent

# 全文件扫描（不依赖 diff，适合审陌生代码 / 迁移前）
ocr scan --path <dir> --format json
```

基线（`--from`）不明确时问用户，别默认猜 `main`。

### 2. 执行并解析

运行命令，解析 JSON。每条 finding 含：

- `category`：`bug` / `security` / `performance` / `maintainability` / `test` / `style` / `documentation` / `other`
- `severity`：`critical` / `high` / `medium` / `low`
- 文件路径与行号

### 3. 汇报

按 severity 从高到低排序，用表格汇报：文件:行、severity、category、问题描述。`critical` / `high` 单独强调。

## 输出格式

```
## ocr 审查结果（<范围>）

共 N 条，critical M 条 / high K 条

| 位置 | 级别 | 类别 | 问题 |
| --- | --- | --- | --- |
| src/foo.go:42 | critical | bug | 空指针解引用 |
| ... | | | |
```

无 finding 时直接说明「ocr 未发现问题」，不编造。

## 边界情况

- ocr 未安装 / 未配 LLM → 走「前置检查」提示，不硬跑。
- ocr 命令返回非预期输出 / 报错 → 原样把 stderr 汇报给用户，不自行脑补结论。
- 用户要求「审完顺手修」→ 可在汇报后逐条提出修复建议；实际改代码走 `workflow-code-generation`，本 skill 不直接改。
