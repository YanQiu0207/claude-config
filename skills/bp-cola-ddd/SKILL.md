---
name: bp-cola-ddd
description: DDD 分层架构最佳实践（语言无关）。覆盖 adapter/application/domain/infrastructure 分层、gateway 边界、DTO 与领域对象分离、扩展点和实体建模。按规模分级：小项目轻量分包，复杂项目完整分层。当进行业务复杂系统的系统设计、架构评审、DDD 改造或分层架构代码审查时使用；包含 Java/COLA 实现参考。
---

> 输出一行：`Using bp-cola-ddd`

# DDD 分层架构最佳实践

## 目标

将 DDD 的「领域驱动、分层架构」思想转成可执行设计和审查规则：先把业务复杂度放到领域模型，再用应用层编排用例，用 gateway 隔离外部依赖，用适配层处理输入输出。

详细依据和 Java/COLA 落地参考见 [references/cola-ddd-practices.md](references/cola-ddd-practices.md)。

## 适用判断

优先使用本 Skill：

- 业务规则多、状态变化多、需要保护不变量。
- 需求涉及多个外部系统、数据库、RPC、消息或第三方 API。
- 代码已经出现入口层（Handler / Controller / Job）里堆业务规则，或 Service 里混合数据访问、HTTP 调用、业务计算。
- 需要把现有 CRUD 代码改造成 DDD / 六边形风格。

不建议强行使用：

- 纯 CRUD、一次性脚本、规则很薄的后台管理页。
- 团队没有能力维护领域模型时；先用轻量分包，避免过度工程。

## 规模分级

**先判断规模，再决定用哪套结构。**

| 规模 | 判断信号 | 推荐结构 |
|---|---|---|
| **轻量** | 规则 < 5 条 / 纯 CRUD / 无多个外部依赖 / 1-2 人维护 | 单包分层（4 个子包） |
| **中等** | 规则 10+ / 多外部依赖 / 需保护不变量 / 跨团队协作 | 多包 + gateway 隔离；引入值对象 |
| **复杂** | 多业务域 / 扩展点需求 / 高变化频率 / 大团队 | 完整多模块 + 聚合根、扩展点、领域事件 |

**轻量结构（单包）**

```text
src/
  adapter/     # 协议适配（HTTP handler、消息消费、定时任务）
  app/         # 用例编排
  domain/      # 实体与规则
  infra/       # 外部依赖实现（持久化、RPC、消息）
```

**完整结构（多模块）**

```text
<service>-client/          # 对外契约（请求/响应对象、领域事件）
<service>-adapter/         # 协议适配
<service>-app/             # 用例编排
<service>-domain/          # 实体、值对象、gateway 接口
<service>-infrastructure/  # gateway 实现、持久化、RPC
```

## 默认工作流

0. **先判断规模**：套用上方分级表，确认用轻量结构还是完整结构，再执行后续步骤。
1. **先定业务域**：按业务能力拆包，不按技术组件拆包；每个包回答「谁拥有这条规则」。
2. **再定用例入口**：把用户动作建模成请求对象（Cmd / Qry / Request），由 application 层暴露服务接口。
3. **把规则推进 domain**：实体、值对象、领域服务维护不变量；application 只编排，不写核心规则。
4. **用 gateway 反转外部依赖**：domain 定义 gateway 接口，infrastructure 实现数据库、RPC、消息和三方 API。
5. **用 adapter 做协议适配**：入口层只组装入参、调用 application、返回响应，不承载业务逻辑。
6. **用通用组件兜底横切能力**：异常、日志、DTO、扩展点、状态机、测试容器优先复用通用组件。

## 分层职责速查

| 层 | 放什么 | 不放什么 |
|---|---|---|
| `adapter` | HTTP Handler、消息消费、定时任务、CLI 等入口适配 | 业务规则、事务脚本、数据库访问 |
| `client` | 对外 API 契约、请求 / 响应对象（Cmd / Qry / DTO）、领域事件定义 | 领域对象、持久化对象、框架实现 |
| `application` | 用例编排、事务边界、校验、调用领域对象和 gateway | 核心业务计算、数据访问 / RPC 细节 |
| `domain` | 实体、值对象、领域服务、领域事件、gateway 接口 | Web / DB / MQ 框架细节 |
| `infrastructure` | gateway 实现、持久化适配（ORM / Repository）、RPC client、消息发送 | 业务不变量、用例流程 |
| `start` / 入口 | 应用启动、DI 装配、配置管理 | 业务逻辑 |

## 建模规则

- **实体拥有行为**：能由对象自己判断和改变的规则，不要外置到贫血 Service。
- **值对象表达概念**：金额、时间段、比例、状态等需要类型化，避免散落原始类型。
- **领域服务处理跨实体规则**：当行为不天然属于单个实体时，才引入领域服务。
- **应用服务一用例一入口**：复杂命令使用独立执行器（CmdExe / Handler）分拆，避免单个 Service 方法过长。
- **Gateway 接口放 domain**：接口说业务需要什么，不说技术怎么拿；实现放 infrastructure。
- **DTO 与持久化对象分离**：DTO 面向调用方，持久化对象面向存储；转换集中放 Convertor / Assembler。

## 设计审查清单

- [ ] 当前规模是否匹配所选结构（轻量 / 完整）？
- [ ] 入口层（Handler / Controller / Job）是否只做协议适配和入参组装？
- [ ] Application 层是否只编排用例，没有核心业务计算和技术细节？
- [ ] 领域对象是否包含关键行为和不变量，而不是只有数据字段？
- [ ] 外部系统是否通过 gateway 接口进入 domain，且实现留在 infrastructure？
- [ ] DTO、持久化对象、Entity 是否分离，转换是否集中？
- [ ] 复杂分支是否需要扩展点或状态机，而不是散落条件判断？

## 反模式

| 反模式 | 改法 |
|---|---|
| 入口层（Handler / Controller）直接调用持久化层 | 入口层 → application service → domain / gateway |
| Application Service 写满业务计算 | 把规则移动到实体、值对象或领域服务 |
| Domain 直接依赖 ORM 框架、HTTP client 或 MQ SDK | Domain 定义 gateway 接口，infrastructure 实现 |
| DTO、持久化对象、Entity 互相复用 | 三者分离，使用 Convertor / Assembler 集中转换 |
| 为所有小需求建完整 DDD 目录 | 先判断规模，轻量需求用轻量分包 |

---

> **Java/COLA 落地参考**：命名约定（`XxxCmdExe`、`XxxGateway`、`XxxDO`）、COLA 组件（扩展点、DTO 基类）、Maven 多模块配置及 Spring 实体托管方案见 [references/cola-ddd-practices.md](references/cola-ddd-practices.md)。
