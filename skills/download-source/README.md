# download-source

多源内容下载工具 —— 把任意 URL 或本地文件统一抓取/转换为本地 Markdown / 字幕 / 音视频，落到 `E:/work/downloads/`。

灵感来自 [joeseesun/qiaomu-anything-to-notebooklm](https://github.com/joeseesun/qiaomu-anything-to-notebooklm)，剥离了 NotebookLM 上传部分，专注「下载资源」一件事。

## 支持的内容源

| 类别 | 来源 | 实现 |
|---|---|---|
| 网页 | 通用 + 300+ 付费墙站点（NYT/WSJ/FT/Economist...） | 6 层级联（jina/defuddle → Googlebot/Bingbot UA + JSON-LD → 多 Referer/EU IP/AMP → archive.today → Google Cache → npx `@teng-lin/agent-fetch@0.1.6`） |
| 微信公众号 | `mp.weixin.qq.com/s/*` | [`url-md`](https://github.com/Bwkyd/url-md) Rust 二进制（主），jina 兜底 |
| X / Twitter | `x.com` / `twitter.com`（含长线程） | 同通用网页 6 层级联 |
| YouTube | `youtube.com` / `youtu.be` | yt-dlp，默认下完整视频+音频+字幕 |
| 播客 | 小宇宙 / 喜马拉雅 / B 站 | Get笔记 OpenAPI（带时间戳全文转写），yt-dlp 兜底音频 |
| 本地文件 | PDF / DOCX / PPTX / XLSX / CSV / JSON / XML / JPG / PNG / MP3 / WAV / ZIP | [markitdown](https://github.com/microsoft/markitdown) |
| 本地文件 | EPUB | [ebooklib](https://github.com/aerkalov/ebooklib) + BeautifulSoup |
| 本地文件 | MD / TXT | 直接复制 |
| 搜索关键词 | 无 URL 无路径 | skill 主对话调 `WebSearch` 拿 URL → 重新走多源混合 |

## 安装

### 1. Python 依赖

> **重要**：本机 PATH 上的 `python` 默认是 3.14，但本技能依赖装在 3.11 下。所有命令都用 Windows Python launcher `py -3.11` 显式指定 3.11。

```powershell
py -3.11 -m pip install -r C:/Users/YanQi/.claude/skills/download-source/requirements.txt
```

### 2. url-md（微信抓取主路径，强烈推荐）

```powershell
irm https://raw.githubusercontent.com/Bwkyd/url-md/main/install.ps1 | iex
```

装到 `%USERPROFILE%\.url-md\bin\url-md.exe`，无需 Chrome。
本技能会自动从 PATH 和上述位置查找 url-md。

### 3. ffmpeg（YouTube 完整视频+音频合并需要）

如果只下字幕（`--youtube-subs-only`），可不装。

PowerShell（winget）：
```powershell
winget install Gyan.FFmpeg
```

### 4. Get 笔记凭证（可选，仅播客转写需要）

环境变量：

```powershell
[Environment]::SetEnvironmentVariable("GETNOTE_API_KEY", "<你的 key>", "User")
[Environment]::SetEnvironmentVariable("GETNOTE_CLIENT_ID", "<你的 client id>", "User")
```

并把浏览器导出的 token 放到：
```
C:\Users\YanQi\.claude\skills\getnote\tokens.json
```
格式见 `lib/podcast_transcript.py` 顶部说明（refresh_token 90 天有效）。

> 凭证缺失时播客自动降级为只下音频（用 yt-dlp），不会硬性失败。

### 5. Node.js（可选，仅 fetch_url 第 6 层 `npx @teng-lin/agent-fetch@0.1.6` 兜底使用）

绝大多数情况下用不上。

第 6 层固定执行 `@teng-lin/agent-fetch@0.1.6` 的 `agent-fetch` bin，避免 `npx --yes` 拉取未锁版本。经 `npm view @teng-lin/agent-fetch version time maintainers repository.url --json` 确认：版本 `0.1.6` 发布时间为 `2026-02-15T03:41:08.260Z`；npm 未提供 `author` 字段，维护者为 `teng-lin <teng.lin@gmail.com>`。来源：[npm package](https://www.npmjs.com/package/@teng-lin/agent-fetch)、[GitHub 仓库](https://github.com/teng-lin/agent-fetch)。

## 验证

```powershell
py -3.11 C:/Users/YanQi/.claude/skills/download-source/scripts/check_env.py
```

## CLI 用法

```powershell
py -3.11 C:/Users/YanQi/.claude/skills/download-source/scripts/download.py <input1> [<input2> ...]
```

| 选项 | 说明 |
|---|---|
| `--out-base DIR` | 输出根目录，默认 `E:/work/downloads/` |
| `--podcast-audio-only` | 播客只下音频，不调 Get 笔记 |
| `--youtube-subs-only` | YouTube 只下字幕（默认下完整视频+音频+字幕） |
| `--no-paywall-bypass` | 禁用付费墙绕过策略，仅 L1 jina |
| `--timeout SEC` | 单源超时，默认 60 |
| `--batch-label TEXT` | 多源时为 batch 目录追加标签 |
| `--force` | 忽略去重索引强制重抓，旧时间戳目录保留 |
| `--no-cache` | 本次既不读也不写去重索引 |

退出码：`0` 全部成功 / `1` 全部失败 / `2` 部分失败 / `75` archive.today 命中 CAPTCHA。

## 去重

默认按规范化 URL 去重，索引存在 `E:/work/downloads/_index.json`。

- 微信文章：剥所有 query（`scene` / `chksm` / `key` / `pass_ticket` 等会话参数）
- YouTube：`youtu.be/x` / `m.youtube.com/watch?v=x` / `shorts/x` 全部统一为 `https://www.youtube.com/watch?v=x`
- X/Twitter：`twitter.com` / `mobile.twitter.com` 统一为 `x.com`，去 query
- 小宇宙/喜马拉雅/B 站：保留 path（episode/BV id），去 query
- 通用网页：剥 `utm_*` / `fbclid` / `gclid` 等追踪参数
- 本地文件：用 `Path.resolve()` 后的绝对路径

命中时 CLI 输出 `"strategy_used": "cached"` 且 `_dir` 指向已有目录，不创建新目录。要重抓加 `--force`（旧目录保留），或手动删 `_index.json` 里对应条目。

## 输出布局

单源：
```
E:/work/downloads/<source_type>/<时间戳>-<slug>/
├── content.md|txt|srt
├── info.json (yt-dlp)
├── *.mp4|*.mp3|...
├── assets/ (图片)
└── meta.json
```

多源：
```
E:/work/downloads/batch-<时间戳>[-label]/
├── batch_meta.json
├── source_01-<type>-<slug>/...
├── source_02-<type>-<slug>/...
└── ...
```

## 触发示例

通过 skill 触发（自然语言）：

- `下载这篇文章 https://mp.weixin.qq.com/s/xxx`
- `把这个付费文章弄下来 https://www.wsj.com/articles/xxx`
- `下载这条推文 https://x.com/user/status/xxx`
- `下载这期播客 https://www.xiaoyuzhoufm.com/episode/xxx`
- `下载这个 YouTube 视频 https://youtube.com/watch?v=xxx`
- `把这个 PDF 转成 Markdown C:/path/to/file.pdf`
- `搜索 "AI 智能体" 并下载相关资料`
- `下载这两个 https://a.com/x https://b.com/y`（多源混合）

直接 CLI：

```powershell
# 单源
py -3.11 scripts/download.py https://mp.weixin.qq.com/s/abc123

# 多源混合
py -3.11 scripts/download.py https://example.com/article.html C:/work/notes.pdf

# 只下字幕
py -3.11 scripts/download.py https://youtube.com/watch?v=xxx --youtube-subs-only

# 播客只下音频
py -3.11 scripts/download.py https://www.xiaoyuzhoufm.com/episode/xxx --podcast-audio-only
```

## 致谢与来源

- [joeseesun/qiaomu-anything-to-notebooklm](https://github.com/joeseesun/qiaomu-anything-to-notebooklm)：原始多源处理器（含 NotebookLM 上传），本技能剥离了上传部分
- [Bwkyd/wexin-read-mcp](https://github.com/Bwkyd/wexin-read-mcp)：微信抓取实现演进史
- [Bwkyd/url-md](https://github.com/Bwkyd/url-md)：当前微信抓取 SOTA（Rust 单二进制）
- [Bypass-Paywalls-Clean](https://gitflic.ru/project/magnolia1234/bpc_uploads)：付费墙绕过域名清单与策略
- [microsoft/markitdown](https://github.com/microsoft/markitdown)：本地多格式 → Markdown
- [aerkalov/ebooklib](https://github.com/aerkalov/ebooklib)：EPUB 解析
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：视频/音频下载
