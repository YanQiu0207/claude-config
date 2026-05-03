---
name: download-source
description: |
  多源内容下载工具：把任意 URL（含付费墙网页、微信公众号、X/Twitter、YouTube、小宇宙/喜马拉雅/B 站播客）或本地文件（PDF、EPUB、Word、PPT、Excel、图片、音频、ZIP、CSV/JSON/XML、Markdown）下载/转换为本地 Markdown 或字幕文件，统一落到 `E:/work/downloads/` 目录。
  当用户说「下载这篇文章」「抓取这个网页」「把这个付费文章弄下来」「下载这条推文」「下载这期播客」「下载这个 YouTube 视频」「把这个 PDF/EPUB/Word 转成 Markdown」「搜索 XX 并下载相关资料」时触发。
  支持一次传多个 URL 或路径做混合下载。
argument-hint: "<URL 或文件路径，多个用空格分隔>"
allowed-tools:
  - Bash
  - Read
  - Write
  - WebSearch
  - Glob
---

当此 skill 生效时，回答第一行固定写：Using skill: download-source

## 输入

用户提供以下任意一种或多种：

- **URL**：网页、付费墙文章、微信公众号、X/Twitter、YouTube、小宇宙、喜马拉雅、B 站
- **本地文件路径**：PDF、EPUB、DOCX、PPTX、XLSX、JPG/PNG/GIF/WebP、MP3/WAV、ZIP、CSV、JSON、XML、MD、TXT
- **搜索关键词**：当输入既不是 URL 也不是已有路径时，按搜索关键词处理

## 处理流程

### 1. 确认依赖与环境

第一次跑前先验证：

```bash
py -3.11 "C:/Users/YanQi/.claude/skills/download-source/scripts/check_env.py"
```

> **重要**：本机 PATH 上的 `python` 命令解析到 Python 3.14（未装依赖），必须用 `py -3.11`（Windows Python launcher）显式指定 3.11，依赖才能加载。所有调用本技能 CLI 的命令都要用 `py -3.11`。

缺依赖时按 `README.md` 指引安装。

### 2. 识别输入类型

| 输入特征 | 路由到 |
|---|---|
| `mp.weixin.qq.com/s/*` | `weixin`（url-md → jina fallback） |
| `youtube.com` / `youtu.be` | `youtube`（yt-dlp 下完整视频+音频+字幕） |
| `xiaoyuzhoufm.com` / `ximalaya.com` / `bilibili.com` | `podcast`（Get笔记 API → yt-dlp 兜底音频） |
| `x.com` / `twitter.com` | `x_twitter`（fetch_url 6 层级联） |
| 其他 `http(s)://` | `webpage`（fetch_url 6 层级联，含付费墙绕过） |
| `*.epub` | `local_epub`（ebooklib） |
| `*.pdf` | `local_pdf`（markitdown） |
| `*.docx` `*.pptx` `*.xlsx` | `local_office`（markitdown） |
| `*.jpg` `*.jpeg` `*.png` `*.gif` `*.webp` | `local_image`（markitdown） |
| `*.mp3` `*.wav` | `local_audio`（markitdown） |
| `*.zip` | `local_zip`（markitdown） |
| `*.csv` `*.json` `*.xml` `*.html` `*.htm` | `local_data`（markitdown） |
| `*.md` `*.txt` | `local_text`（直接复制） |
| 其他（无 URL 无路径） | `search`（见下） |

### 3. 处理搜索关键词路径

当用户输入是搜索关键词（非 URL 非路径）时：

1. 调用 `WebSearch` 工具，搜索关键词，取前 5-8 个结果的 URL
2. 把这批 URL 作为多源混合输入传给 CLI
3. 在 batch_meta.json 里记录原始搜索关键词

### 4. 调用 CLI 下载

单源或多源都用同一个 CLI：

```bash
py -3.11 "C:/Users/YanQi/.claude/skills/download-source/scripts/download.py" <input1> [<input2> ...]
```

可选参数：

- `--out-base <DIR>`：自定义输出根目录，默认 `E:/work/downloads/`
- `--podcast-audio-only`：播客只下音频，不调 Get 笔记 API
- `--youtube-subs-only`：YouTube 只下字幕，不下视频/音频
- `--no-paywall-bypass`：禁用付费墙绕过策略，仅 L1 jina
- `--timeout <秒>`：单源超时，默认 60
- `--batch-label <TEXT>`：多源时为 batch 目录追加标签
- `--force`：忽略去重索引，强制重新下载（默认行为：URL 规范化后命中索引则跳过，返回旧路径）
- `--no-cache`：本次执行既不读也不写去重索引

### 去重行为

CLI 默认开启基于 URL 规范化的去重：

- 同一篇微信文章不同 `scene/chksm` 参数 → 视为同一资源，第二次自动跳过
- YouTube `youtu.be/x` / `m.youtube.com/watch?v=x` / `shorts/x` → 都规范化为 `youtube.com/watch?v=x`
- X/Twitter 各 host 统一为 `x.com/<user>/status/<id>`
- 通用网页：剥掉 `utm_*`、`fbclid` 等追踪参数

命中时返回 `"strategy_used": "cached"`，`_dir` 指向已有目录，不创建新目录。需要重抓时显式加 `--force`。

### 5. 报告结果

下载完成后，读取并展示 `meta.json` 摘要：

- 单源：列出 `title`、`source_type`、`strategy_used`、产出文件路径
- 多源：表格汇总每个源的状态（成功/失败/降级）+ 整体 batch 目录路径

如有付费墙 CAPTCHA 阻塞（`strategy_used: archive_captcha`），明确告知老板并提供 archive.today URL，让老板手动开页解 CAPTCHA 后再次重试。

## 输出格式

### 单源输出

```
E:/work/downloads/<source_type>/<时间戳>-<slug>/
├── content.md              # 主内容（webpage/weixin/x_twitter/local_*）
├── transcript.txt          # 纯文本（podcast 转写）
├── <video_id>.<lang>.srt   # 字幕（youtube）
├── <video_id>.info.json    # yt-dlp 原始元数据（youtube）
├── <video_id>.<ext>        # 视频文件（youtube）
├── <media_id>.mp3          # 音频文件（podcast 兜底）
├── assets/                 # 图片等附属资源（weixin/网页含图）
└── meta.json               # 统一元数据（见下）
```

### 多源输出

```
E:/work/downloads/batch-<时间戳>/
├── batch_meta.json
├── source_01-<type>-<slug>/
│   └── ... (同单源结构)
├── source_02-<type>-<slug>/
│   └── ...
└── ...
```

### meta.json 字段

```json
{
  "source_type": "webpage|weixin|x_twitter|youtube|podcast|local_pdf|local_epub|local_office|local_image|local_audio|local_zip|local_data|local_text",
  "input": "原 URL 或路径",
  "title": "...",
  "fetched_at": "2026-05-03T12:34:56+08:00",
  "strategy_used": "jina|defuddle|googlebot|bingbot|amp|archive|google_cache|agent_fetch|url_md|getnote|yt_dlp_youtube|yt_dlp_podcast_audio|markitdown|ebooklib|copy",
  "paywall_bypassed": true,
  "files": ["content.md", "assets/cover.jpg"],
  "size_bytes": 123456,
  "extras": {}
}
```

失败或跳过时，`strategy_used` 可能是 `cached`、`search_pending`、`unknown`、`exception`、`archive_captcha`，或带 `_failed`、`_missing`、`_timeout`、`_empty` 后缀的失败原因。

## 边界情况

1. **付费墙 archive.today CAPTCHA**：CLI 退出码 75 + stderr 提示 `ARCHIVE_CAPTCHA:<url>`。skill 必须把这条提示完整转给老板，让老板手动开页解 CAPTCHA 后再次执行同样命令。
2. **微信文章被反爬挡住**：url-md 失败 → 自动 fallback jina。两条都失败时返回 `strategy_used: failed` + stderr 完整内容。
3. **播客 Get笔记 env 未配置**：自动降级到 `--podcast-audio-only`（用 yt-dlp 抓音频本体），meta 里标 `extras.degraded: true`。
4. **YouTube 大视频**：默认下完整视频+音频+字幕，文件可能很大（单视频几百 MB 到几 GB）。如果老板只要字幕，加 `--youtube-subs-only`。
5. **本地路径不存在**：报错前先确认是否被识别成搜索关键词（路径里有空格、引号、特殊字符可能漏判）。
6. **混合多源中部分失败**：不中断剩余源，最终在 batch_meta 里逐个标状态。所有源都失败时整体退出码非 0。
7. **输出目录冲突**：时间戳精确到秒，理论上不冲突；如冲突追加 `-2`、`-3` 后缀。

## 安装与配置

详见 `~/.claude/skills/download-source/README.md`。一次性安装清单：

1. `pip install -r ~/.claude/skills/download-source/requirements.txt`
2. PowerShell 装 url-md：`irm https://raw.githubusercontent.com/Bwkyd/url-md/main/install.ps1 | iex`
3.（可选）配置 Get笔记环境变量：`GETNOTE_API_KEY` / `GETNOTE_CLIENT_ID` + `~/.claude/skills/getnote/tokens.json`
4.（可选）系统装 Node.js（让 fetch_url L6 兜底 `npx @teng-lin/agent-fetch@0.1.6` 可用）

## 不做什么

明确不在本 skill 范围内（如有需要请用其他工具）：

- 不上传到 NotebookLM / 飞书 / 任何云端
- 不做内容总结、改写、翻译
- 不生成播客 / PPT / 思维导图 / Quiz
- 不做深度分析提问
