# workflow-code-review 触发评估用例

> 评测体系 Tier 1（触发评估）的**样板**，对应 [docs/08-evaluation-strategy.md](../../../docs/08-evaluation-strategy.md) §5.1。
> 目标：验证 `description` 能让本 skill 在「该审代码」时被召回、在 near-miss 场景不误触发。
> 判定方式（确定性）：执行 transcript 是否出现首行标记 `Using workflow-code-review`。
> 跑法目前是人工 / AI 半自动（喂 prompt → 看是否触发），不依赖 LLM judge，几乎零 token。

## should-trigger（应触发，测召回）

| ID | 用户输入 | 预期 | 理由 |
| --- | --- | --- | --- |
| T-1 | 「帮我 review 一下这次的改动」 | 触发 | 直接的代码评审请求 |
| T-2 | 「这段 auth 代码有没有安全问题或者 bug？」 | 触发 | 多维度审查诉求（安全 + 健壮性），正是分级 review 的范围 |
| T-3 | 「合入前帮我把 `payment/` 下这次提交审一遍」 | 触发 | 指定范围 + merge 前把关，标准 review 场景 |

## should-not-trigger（不应触发，测误报；含 near-miss）

| ID | 用户输入 | 预期 | 应改走 | 理由 |
| --- | --- | --- | --- | --- |
| N-1 | 「帮我把这个空指针 bug 改掉」 | 不触发 | `workflow-code-generation` | 诉求是「改代码」，不是「审代码」——最易混的 near-miss |
| N-2 | 「这段代码是什么意思，讲解一下」 | 不触发 | （代码讲解，无 skill） | 要的是解释，不产出审查报告 |
| N-3 | 「给这个模块补一下单元测试」 | 不触发 | `workflow-test-generation` | 测试生成，不是评审 |

## boundary（边界，允许澄清而非强行触发）

| ID | 用户输入 | 预期 | 理由 |
| --- | --- | --- | --- |
| B-1 | 「帮我看看这个文件」 | 先澄清 | 意图不明：可能是 review，也可能是讲解 / 改写。强行触发 review 即误报 |
| B-2 | 「发布前帮我检查一下」 | 先澄清范围 | 可能涉及 review + 机器验证 + 测试多道，需确认要哪些，不应默认只跑 review |

## 参考指标（经验值，非硬标准）

- 触发准确率（should-trigger 命中）：> 90%。
- 误触发率（should-not-trigger 命中）：< 5%。
- 边界样本：以「询问澄清」为正确，不计入误触发。

> 效果评估（这次审查有没有抓到该抓的问题）属 Tier 2，成本高、需 Rubric + 基线，按需再建 `quality-cases.md` / `rubric.md` / `baseline/`，本样板不预置空壳。

## profile-routing（档位路由）

| ID | 场景 | 预期 reviewer | 理由 |
| --- | --- | --- | --- |
| P-1 | 局部低风险修复 | `comprehensive-reviewer` | `lightweight` 单 Reviewer |
| P-2 | 风险可控的普通功能或跨模块修改 | `comprehensive-reviewer` | `standard` 单 Reviewer |
| P-3 | 安全、权限、数据迁移、并发或公共 API | 全量 5 Reviewer | `strict` 保留多维审查与 Critic |
