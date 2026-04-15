---
name: kms-knowledge-assistant
description: Use when Codex should answer user questions from the local personal knowledge base as a normal working skill, not as an API test. Trigger for requests like "查一下我的知识库", "根据我的笔记回答", "从本地知识库找资料", or "用个人知识库支持当前任务". The skill uses the local kms-api at http://127.0.0.1:49153 and prefers /ask for answer generation, /search for retrieval-only tasks, and /verify for citation checks.
---

# KMS Knowledge Assistant

本 skill 用于正式使用本地个人知识库，不是接口验收脚本。

默认服务：

- `http://127.0.0.1:49153`

## 使用原则

1. 用户要“回答问题”时，优先调用 `POST /ask`。
2. 用户只要“找资料 / 看候选片段”时，调用 `POST /search`。
3. 用户要求“校验引用是否可靠”时，调用 `POST /verify`。
4. 默认只发起 `1` 次 HTTP 调用：直接调用 `POST /ask`，不要为了自检而先跑 `/search`，也不要在未满足条件时补第二次 `/ask`。
5. 只有满足以下条件之一，才允许额外调用接口：
   - `/ask` 返回 `abstained=true`
   - 用户明确要求“只查资料 / 看检索结果 / 校验引用”
   - 第一次 `/ask` 的返回明显暴露出 query 写偏了，且不重试就无法可靠回答
6. 若 `/ask` 返回 `abstained=true`，直接回复：`资料不足，无法确认。`；除非用户明确要求继续检索，否则不要自动补 `/search`。
7. 若 `/ask` 返回 `abstained=false`，默认先把 `sources` 当作定位线索，再补读命中的原文后组织最终答案；不要只停留在 chunk 片段。
8. 默认适度展开回答，不要只回一句短答。
9. 默认补读是有边界的：优先读取 `sources` 命中的文件、命中标题及相邻标题，不做无边界扩搜。
10. 若问题属于“有几种 / 分几类 / 请列全 / 枚举全部方案 / 统计数量”这类枚举型问题，默认要检查同一文档的标题结构，避免 top-k 漏掉并列小节。
11. 若用户明确要求“只按 /ask 返回内容回答”或“不要读原文”，则禁止补读，直接按 `prompt` 与 `sources` 回答。
12. 即使用户强调“读原文”，默认也只做与 `sources` 绑定的有边界原文补读，不扩展成整篇全文阅读工作流。
13. 进入本 skill 时就记录开始时间；最终回复末尾追加整个 skill 的总耗时，例如：`技能耗时：1.8s`。

## 标准工作流

### 1. 直接问答

- 进入 skill 后立即记录开始时间
- 先构造问题 `question`
- 再生成 1 到 3 条检索查询 `queries`
- 调用 `1` 次 `/ask`
- 先看 `/ask` 返回的 `sources`
- 再读取命中的原文：优先读命中文件、命中标题、相邻标题或相邻段落
- 最后由宿主 LLM 基于 `prompt + sources + 已补读原文` 组织答案
- 若用户明确要求只看 `/ask` 结果，则跳过补读
- 除非出现拒答、用户明确要求检索结果、或第一次 query 明显写偏，否则不要补 `/search`，也不要再次调用 `/ask`
- 回复末尾追加整个 skill 的总耗时，统计范围包含接口调用、原文补读和答案组织

示例：

```bash
curl -s http://127.0.0.1:49153/ask \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary @E:/github/mykms/scripts/ask-context.json
```

### 2. 只查资料

- 调用 `/search`
- 阅读返回的 `results`
- 按需继续追问或改写 query

示例：

```bash
curl -s http://127.0.0.1:49153/search \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary @E:/github/mykms/scripts/search-context.json
```

### 3. 引用校验

- 当已经拿到答案和 `chunk_id` 时
- 调用 `/verify`

示例：

```bash
curl -s http://127.0.0.1:49153/verify \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary @E:/github/mykms/scripts/verify-context.json
```

## 查询策略

- `question` 用自然语言，贴近用户原问题。
- `queries` 不只是原问题复制，而是为检索服务的“召回表达”。
- `queries` 里至少放一条原问题改写。
- 若主题明确，可再补 1 到 2 条术语型查询。
- 若问题明显超出语料范围，不要硬答；允许走拒答。
- 对“有几种 / 分几类 / 列出全部”类问题，优先把查询词写成“主题 + 分类 / 类型 / 方案 / 全部 / 对比”等形式，先尽量让 `/ask` 自己召回完整结构。
- `/ask` 返回后，不要立刻停在 chunk 文本；先把它当作“读原文入口”。
- 对“概念 / 分类 / 对比 / 原理”类问题，默认按以下顺序适度展开：
  - 先给直接结论
  - 再补分类或核心差异
  - 最后补适用场景或关键注意点
- 除非用户明确要求极简，否则不要只输出一句话。

## 生成 `queries` 的原则

- 先判断用户原问题是否“适合直接检索”：
  - 若问题已经明确、术语充分、信息量够，保留一条接近原问的 query 即可。
  - 若问题很短、很口语、很模糊、代词多、上下文省略严重，先改写再检索。
- 默认采用“扩展改写”：
  - 把口语化问法改成知识库更可能出现的书面表达。
  - 补足被省略的对象、动作、条件、范围。
  - 例：`怎么退` 可改成 `商品退货的流程、条件和注意事项`。
- query 质量要尽量在第一次调用前解决，不要把 `/search` 当作直接问答的默认前置诊断步骤。
- 默认让多条 query 形成“互补”，不要只是同义词堆叠：
  - 一条保留用户意图的自然问句。
  - 一条改写成知识库风格的完整表述。
  - 一条拆成术语维度或子问题。
- Multi-Query 的常见拆法：
  - 按流程拆：`流程`、`步骤`、`操作方式`
  - 按条件拆：`条件`、`限制`、`适用范围`
  - 按责任拆：`费用承担`、`审批人`、`前置要求`
  - 按别名拆：同一概念在知识库中的正式叫法、缩写、业务术语
- 当问题特别短、召回明显不稳、或知识库表述偏书面时，可加入一条 HyDE 风格 query：
  - 先写一小句“假设性答案”或“知识库里可能出现的描述”，再把它当作 query。
  - 这条 query 应是高信息密度的描述，不要写成长段落，不要变成真正作答。
  - 例：`用户申请商品退货时，需要满足退货条件，并按流程提交申请、审核和退款。`
- 控制 query 数量，默认 1 到 3 条：
  - 简单问题 1 到 2 条即可。
  - 口语化、模糊、低信息量问题优先补满到 3 条。
  - 除非有明确必要，不要生成大量近似 query。
- query 设计目标是“提高召回覆盖面”，不是“提前回答用户问题”。
- 若问题强依赖上文语境，先把上下文补全到 query 里，再送检索；不要把脱离上下文的短句直接拿去搜。
- 若用户使用明显非知识库术语的说法，优先补一条知识库可能采用的正式术语 query。

## 补读边界

- “补读”默认开启，但只用于把 `sources` 扩展到命中原文，不用于重新做一套独立检索。
- 补读优先级：
  - 先看 `sources[*].title_path`
  - 再看同一文件的标题结构
  - 只在必要时读取命中的相邻小节
- 默认不要把原文理解成“整个知识库全文”；补读范围仍应绑定在 `/ask` 命中的文件和主题上。
- 若补读发现 `/ask` 漏了同一文档中的并列项，回答中应直接整合这些内容，不必把 chunk 和原文人为拆成两套答案。

## Git Bash 建议

- 不要在命令行里手写中文 JSON。
- 始终使用 `--data-binary @file.json`。
- 可直接复用仓库里的请求样例：
  - `E:/github/mykms/scripts/ask-context.json`
  - `E:/github/mykms/scripts/ask-vector-clock.json`
  - `E:/github/mykms/scripts/search-context.json`
  - `E:/github/mykms/scripts/verify-context.json`

## 参考

- API 契约：`E:/github/mykms/app/adapters/reference/api.md`
- 项目说明：`E:/github/mykms/README.md`
