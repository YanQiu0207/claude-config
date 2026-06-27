# COLA DDD 落地参考

## 来源基线

本参考来自本地仓库 `E:/github/COLA`，当前读取到的 commit 为 `d948f204d58fe7bd30a3ac919308a1311b76fec5`。如果 COLA 升级或文件行号变化，先重新检索源码再复用结论。

## COLA 的核心思想

- COLA 是 `Clean Object-Oriented and Layered Architecture`，即「整洁面向对象分层架构」。来源：`README.md:16-17`。
- COLA 把应用架构视为「要素结构」，目标是定义结构、治理复杂度、降低系统熵值。来源：`README.md:29-42`。
- COLA 与六边形、洋葱、整洁架构的共同点是「以业务为核心，解耦外部依赖，分离业务复杂度和技术复杂度」。来源：`README.md:52-54`。
- COLA 不只给思想，也提供 archetype 和组件作为落地工具。来源：`README.md:54-59`、`README.md:63-74`。

## 架构骨架

### 标准多模块形态

`cola-archetype-web` 生成以下模块：

```text
client
adapter
app
domain
infrastructure
start
```

证据：`cola-archetypes/cola-archetype-web/src/main/resources/archetype-resources/pom.xml:25-31`。

`cola-archetype-service` 去掉 `adapter`，保留后端服务模块：

```text
client
app
domain
infrastructure
start
```

证据：`cola-archetypes/cola-archetype-service/src/main/resources/archetype-resources/pom.xml:25-30`。

v5 还增加了 `cola-archetype-light`，支持基于 package 的轻量级分层。证据：`README.md:120-124`。

### 依赖关系的现实约束

COLA 示例不是教科书式「domain 完全零依赖」：

- `app` 依赖 `client` 和 `infrastructure`。证据：`cola-archetypes/cola-archetype-web/src/main/resources/archetype-resources/__rootArtifactId__-app/pom.xml:15-23`。
- `domain` 依赖 `client`、`cola-component-domain-starter` 和 `cola-component-exception`。证据：`cola-archetypes/cola-archetype-web/src/main/resources/archetype-resources/__rootArtifactId__-domain/pom.xml:15-31`。
- `infrastructure` 依赖 `domain` 并接入 MyBatis、MySQL、JSON 等技术依赖。证据：`cola-archetypes/cola-archetype-web/src/main/resources/archetype-resources/__rootArtifactId__-infrastructure/pom.xml:15-38`。
- `start` 依赖 `adapter` 并负责启动装配。证据：`cola-archetypes/cola-archetype-web/src/main/resources/archetype-resources/start/pom.xml:15-38`。

实践建议：如果团队追求更严格的 Clean Architecture，可把 `app -> infrastructure` 收紧为运行时装配；如果团队更看重 Spring 落地成本，保留 COLA 这种工程化折中。

## 各层职责

### Adapter：协议适配

Controller 只创建请求对象并调用 application service。示例中 `ChargeController` 把 path / request param 转成 `BeginSessionRequest`、`ChargeRequest`、`EndSessionRequest`，然后调用 `chargeService`。证据：`cola-archetypes/cola-archetype-light/src/main/resources/archetype-resources/src/main/java/adapter/ChargeController.java:20-47`。

### Application：用例编排

`ChargeServiceImpl` 负责读取 session、调用 account / charge gateway、调用领域对象 `Account.charge`，最后返回 `Response`。证据：`cola-archetypes/cola-archetype-light/src/main/resources/archetype-resources/src/main/java/application/ChargeServiceImpl.java:39-92`。

复杂命令可以拆到 `XxxCmdExe`：`MetricsServiceImpl` 注入多个 `CmdExe` / `QryExe`，每个公开方法转发到对应 executor。证据：`cola-samples/craftsman/craftsman-app/src/main/java/com/alibaba/craftsman/service/MetricsServiceImpl.java:21-88`。

### Domain：业务对象和不变量

`Account` 是领域实体，包含余额、套餐、扣费行为和余额检查；`charge` 方法组装规则并同步账户系统。证据：`cola-archetypes/cola-archetype-light/src/main/resources/archetype-resources/src/main/java/domain/account/Account.java:25-85`。

`MetricItem` 是抽象领域实体，包含所属指标、指标所有者和转换 JSON 的领域行为。证据：`cola-samples/craftsman/craftsman-domain/src/main/java/com/alibaba/craftsman/domain/metrics/MetricItem.java:16-45`。

### Gateway：外部依赖边界

Gateway 接口表达领域需要什么：`AccountGateway` 定义获取账户和同步扣费记录。证据：`cola-archetypes/cola-archetype-light/src/main/resources/archetype-resources/src/main/java/domain/gateway/AccountGateway.java:11-32`。

Infrastructure 实现 gateway，并把调用变成具体 HTTP / DB / RPC 操作：`AccountGatewayImpl` 实现 `AccountGateway`，内部使用 `RestClient` 调外部账户系统。证据：`cola-archetypes/cola-archetype-light/src/main/resources/archetype-resources/src/main/java/infrastructure/AccountGatewayImpl.java:22-48`。

`MetricGatewayImpl` 实现 `MetricGateway`，调用 `MetricMapper`、RPC mapper，并发布领域事件。证据：`cola-samples/craftsman/craftsman-infrastructure/src/main/java/com/alibaba/craftsman/gatewayimpl/MetricGatewayImpl.java:37-66`。

### DTO / Response：边界契约

COLA 组件定义了请求和响应基类：

- `Command` 是「client 发来的请求」。证据：`cola-components/cola-component-dto/src/main/java/com/alibaba/cola/dto/Command.java:3-13`。
- `Query` 继承 `Command`。证据：`cola-components/cola-component-dto/src/main/java/com/alibaba/cola/dto/Query.java:3-13`。
- `Response` 包含 `success`、`errCode`、`errMessage` 和成功 / 失败工厂方法。证据：`cola-components/cola-component-dto/src/main/java/com/alibaba/cola/dto/Response.java:8-59`。
- `SingleResponse` 和 `MultiResponse` 分别包装单条和多条数据。证据：`cola-components/cola-component-dto/src/main/java/com/alibaba/cola/dto/SingleResponse.java:8-41`、`cola-components/cola-component-dto/src/main/java/com/alibaba/cola/dto/MultiResponse.java:14-61`。

## 领域实体托管

`cola-component-domain-starter` 的 `@Entity` 同时是 Spring `@Component`，作用域是 prototype，并注释说明实体不是线程安全对象。证据：`cola-components/cola-component-domain-starter/src/main/java/com/alibaba/cola/domain/Entity.java:9-20`。

`DomainFactory.create` 通过 `ApplicationContextHelper.getBean` 创建实体。证据：`cola-components/cola-component-domain-starter/src/main/java/com/alibaba/cola/domain/DomainFactory.java:9-13`。

`ApplicationContextHelper` 优先按 type 找 bean，找不到再按首字母小写的 bean name 找。证据：`cola-components/cola-component-domain-starter/src/main/java/com/alibaba/cola/domain/ApplicationContextHelper.java:23-40`。

实践建议：只有当领域对象确实需要注入 gateway / domain service 时，才使用 Spring 托管实体；否则优先普通构造器和工厂方法，降低框架耦合。

## 扩展点模式

当同一个业务点在不同业务身份、用例、场景下有不同实现时，使用扩展点，而不是在 application 或 domain 里堆条件分支。

- `ExtensionPointI` 明确说明扩展点表示「一块逻辑在不同的业务有不同的实现」。证据：`cola-components/cola-component-extension-starter/src/main/java/com/alibaba/cola/extension/ExtensionPointI.java:3-8`。
- `@Extension` 提供 `bizId`、`useCase`、`scenario` 三个维度。证据：`cola-components/cola-component-extension-starter/src/main/java/com/alibaba/cola/extension/Extension.java:18-25`。
- `ExtensionExecutor` 的定位顺序是完整场景、默认 scenario、默认 use case + 默认 scenario，找不到则抛异常。证据：`cola-components/cola-component-extension-starter/src/main/java/com/alibaba/cola/extension/ExtensionExecutor.java:39-78`。
- `ExtensionRegister` 要求扩展点接口名包含 `ExtPt`，并禁止重复注册同一坐标。证据：`cola-components/cola-component-extension-starter/src/main/java/com/alibaba/cola/extension/register/ExtensionRegister.java:46-58`、`cola-components/cola-component-extension-starter/src/main/java/com/alibaba/cola/extension/register/ExtensionRegister.java:92-106`。

## 代码组织建议

### 命名

| 类型 | 建议命名 | 例子 |
|---|---|---|
| Command | `XxxCmd` | `UserProfileAddCmd` |
| Query | `XxxQry` | `ATAMetricQry` |
| 用例执行器 | `XxxCmdExe` / `XxxQryExe` | `SharingMetricAddCmdExe` |
| Gateway 接口 | `XxxGateway` | `MetricGateway` |
| Gateway 实现 | `XxxGatewayImpl` | `MetricGatewayImpl` |
| 持久化对象 | `XxxDO` | `MetricDO` |
| 客户端对象 | `XxxCO` / `XxxDTO` | `ATAMetricCO` |
| 转换器 | `XxxConvertor` / `XxxAssembler` | `MetricConvertor` |

### 包结构

复杂服务优先使用多模块：

```text
<artifact>-client
<artifact>-adapter
<artifact>-app
<artifact>-domain
<artifact>-infrastructure
start
```

小服务优先使用轻量分包：

```text
adapter/
application/
domain/
infrastructure/
```

### 用例代码形态

```text
adapter/Controller
    -> application/ServiceI
        -> application/command/XxxCmdExe
            -> domain/entity 或 domain service
            -> domain/gateway/XxxGateway
                -> infrastructure/gatewayimpl/XxxGatewayImpl
```

## 设计取舍

- **COLA 的强项**：结构明确、适合 Java / Spring 团队、archetype 和组件能降低落地成本。
- **COLA 的代价**：层和对象变多，小需求容易显得重；如果只是 CRUD，优先使用轻量分包。
- **最大的误用**：只复制目录结构，不把业务规则推进 domain；这样只会得到「分层贫血模型」。
- **最小落地策略**：先从 gateway 边界、DTO / DO / Entity 分离、核心实体行为三个点做起，不要一口气重构全仓。

## 审查问题清单

1. 当前修改属于哪个业务域？包名是否体现业务语言？
2. 入口对象是 `Cmd` / `Qry` / `Request`，还是直接把 HTTP / DB 模型泄漏进用例？
3. 关键规则在 domain，还是散落在 Controller、Mapper、GatewayImpl？
4. Gateway 接口是否从业务语义命名，而不是从技术实现命名？
5. 是否存在 DTO、DO、Entity 互相复用导致边界泄漏？
6. 是否有明显的分支膨胀，应该改成扩展点、策略或状态机？
7. 这次改动是否值得完整 DDD 分层，还是轻量分包即可？
