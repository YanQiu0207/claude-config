---
name: fuwari-post
description: |
  将一个 Markdown 源文件迁移到 Fuwari 博客的 posts 目录，并完成图片本地化和 frontmatter 生成。当用户要求"把这篇 md 复制到博客"、"发布到 Fuwari"、"迁移文章到 posts 目录"等场景时触发。
  每篇文章以目录形式组织（`posts/<slug>/index.md` + 同目录图片）。本地图片复制、网络图片下载，正文内图片链接全部改为相对路径 `./xxx`。
  frontmatter 每次主动生成：title / published / updated / description / tags / category / draft / lang。
  仅处理单个文件。多文件、目录、通配符请使用 `batch-fuwari-post`。
argument-hint: "<源 md 路径> [目标 posts 根目录]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
model: sonnet
---

当此 skill 生效时，回答第一行固定写：Using skill: fuwari-post

> **⚠ 并发安全**：本技能被 `batch-fuwari-post` 通过多个并行后台 agent 同时调用，每个 agent 处理不同文件。严禁使用固定名称的临时文件或全局共享状态；所有中间产物必须绑定到目标 slug 目录下。

## 输入

- **必填**：源 Markdown 文件的绝对路径
- **可选**：目标 posts 根目录（默认 `E:/github/yanqiu0207.github.io/src/content/posts`）

如果用户只给了文件名而非绝对路径，先用 Glob 工具定位唯一匹配的文件；多匹配时列出让用户选择。

## 处理流程

### 步骤 1：读取源文件与路径解析

1. 用 Read 工具读取源文件内容
2. 确定 **slug**（目标目录名）：
   - 源文件名去扩展名即为 slug（例如 `logic-clock.md` → `logic-clock`）
   - 若 slug 含中文或空格，转为 kebab-case 的英文或拼音；无法转换时保留原名
3. 确定**源文件所在目录**（用于解析本地图片的相对路径）
4. 目标目录路径 = `<posts_root>/<slug>/`

### 步骤 2：扫描图片引用

用 Grep 或正则提取所有图片引用，注意以下两种语法：

- Markdown：`![alt](path)` 或 `![alt](path "title")`
- HTML：`<img src="path" ...>`

对每个图片链接分类：

| 类型 | 判断 | 后续处理 |
|------|------|---------|
| 网络图片 | 以 `http://` 或 `https://` 开头 | 下载 |
| 本地绝对路径 | 以 `/`、盘符（`X:`）开头 | 复制 |
| 本地相对路径 | 其他 | 相对源文件目录解析后复制 |
| `data:` base64 | 以 `data:` 开头 | 保留原样，不处理 |

### 步骤 3：创建目标目录

```bash
mkdir -p "<posts_root>/<slug>"
```

### 步骤 4：图片迁移

对每张图片：

1. **派生目标文件名**：取 URL/路径的 basename（去除查询参数）；若为空或不安全字符，生成 `img-<序号>.<推测扩展名>`
2. **去重**：若目标目录已有同名文件，附加 `-2`、`-3` 等后缀
3. **网络图片**：`curl -fsSL -o "<target>/<filename>" "<url>"`
   - 失败时记录到报告，不中断流程
4. **本地图片**：`cp "<abs_source>" "<target>/<filename>"`
   - 源文件不存在时记录到报告，不中断流程
5. 记录下来「原链接 → 新相对路径 `./<filename>`」的映射

如果文章没有任何图片，跳过本步骤。

### 步骤 5：生成 frontmatter

**每次主动生成**，即使源文件已有 frontmatter 也重新生成（但保留源 frontmatter 中用户明确设置的字段作为候选）。字段规则：

| 字段 | 必填 | 生成规则 |
|------|------|---------|
| `title` | 是 | 取文档第一个 `#` 或 `##` 标题；若无，取 slug 去连字符后的可读形式 |
| `published` | 是 | 今天的日期，格式 `YYYY-MM-DD`（通过 `date +%F` 获取） |
| `updated` | 是 | 同 `published` |
| `description` | 是 | 阅读全文后生成一句话摘要（15–60 字，概括文章核心主题与价值） |
| `tags` | 是 | 根据内容推断 3–6 个标签（技术栈、领域、关键概念） |
| `category` | 是 | 根据内容推断一个分类（如"分布式基础"、"算法"、"AI"、"工具"、"生活随笔"等） |
| `draft` | 是 | `false` |
| `lang` | 是 | `zh_CN` |

frontmatter 输出格式（严格遵守）：

```yaml
---
title: 逻辑时钟
published: 2026-04-12
updated: 2026-04-12
description: Lamport 逻辑时钟在分布式系统中基于 Happened-Before 关系为事件定序。
tags: [分布式系统, 一致性, Lamport]
category: 分布式基础
draft: false
lang: zh_CN
---
```

### 步骤 6：改写正文并写入 index.md

1. 若源文件本身带有 frontmatter（`---` 包围块），**去掉整个 frontmatter 块**
2. 对正文中的每个图片引用，按步骤 4 的映射表替换为 `./<filename>`
3. 在正文顶部拼接新生成的 frontmatter
4. 用 Write 工具写入 `<posts_root>/<slug>/index.md`

### 步骤 7：完成报告

向用户汇总：

- 目标目录：`<posts_root>/<slug>/`
- 图片总数：N（本地复制 A 张 / 网络下载 B 张 / 失败 C 张）
- 生成的 frontmatter 字段摘要（title、tags、category）
- 失败项列表（如有）

## 边界情况

- **源文件不存在**：直接报错，不创建任何目标文件
- **目标目录已存在且非空**：告知用户，询问是覆盖还是中止（批量模式下默认覆盖 `index.md` 和已存在的图片，不清理多余文件）
- **slug 冲突**：同名目录已经是其他文章 → 报错让用户决定
- **图片文件名含中文或特殊字符**：保留原文件名，URL-decode 后做安全化处理（替换空格为 `-`）
- **HTML `<img>` 标签混用**：同样迁移链接并替换 src 属性
- **全篇无图片**：跳过步骤 4，其他步骤正常
- **URL 无扩展名 / Content-Type 无法确定**：默认用 `.png`，在报告中提示用户手工核对

## 输出的标准消息格式

```
✓ 迁移完成：<slug>
  目标：E:/github/yanqiu0207.github.io/src/content/posts/<slug>/index.md
  图片：3 张（本地 1 / 下载 2 / 失败 0）
  frontmatter：title="逻辑时钟" | category="分布式基础" | tags=[分布式系统, 一致性, Lamport]
```

若有失败项，在消息下方追加失败列表。
