# YuanQi 后端说明

`backend/` 是项目的业务信任边界，基于 Spring Boot 3 和 JDK 17。浏览器的所有业务请求都先到这里：后端验证 JWT、执行行级权限控制、读写 MySQL，并在需要时将已验证的 JWT 转发给内网 Agent。

## 后端负责什么？

- 用户登录、首次修改密码和 JWT 签发/校验。
- 患者、病历、处方的增删改查，以及按租户、科室和本人范围过滤数据。
- 临时患者授权、写请求幂等、审计记录、反馈、通知和会话存储。
- 处方状态的 Flowable 审批流程。
- 处方分析快照：只向 Agent 提供去标识化、字段受限的数据。
- 代理 Agent 的 SSE 对话、检查报告解析和医学知识图谱请求；浏览器不直接连接 Python。

## 本地运行

前提：已在项目根目录执行 `docker compose up -d mysql redis neo4j`，并已复制根目录 `.env.example` 为 `.env`。

```powershell
Set-Location backend
mvn spring-boot:run "-Dspring-boot.run.profiles=dev"
```

- 服务地址：`http://localhost:8080`
- OpenAPI / Swagger：`http://localhost:8080/swagger-ui.html`
- 健康检查：`http://localhost:8080/actuator/health`

首次连接到空 MySQL 时，Flyway 会自动执行数据库 migration，创建项目需要的表和无敏感信息的演示账号。它不会连接或覆盖其他人的数据库。

## 本地演示登录

开发环境可使用：

| 项目 | 值 |
| --- | --- |
| 用户名 | `yu_ming_demo` |
| 初始密码 | `123456` |
| 首次登录 | 必须修改密码 |

开发账号只用于本地演示。生产环境必须接入正式身份认证和用户目录，不能使用这些账号或固定密码。

## 权限与数据范围

JWT 中至少包含以下已验证声明：

| 声明 | 示例 | 作用 |
| --- | --- | --- |
| `sub` | `1010` | 当前用户 ID。 |
| `tenant_id` | `1` | 租户隔离边界。 |
| `data_scope` | `ALL` / `DEPARTMENT` / `SELF` | 决定可访问的业务数据范围。 |
| `department_ids` | `[10, 20]` | 当前用户可访问或分配的科室。 |
| `permissions` | `["patient:read"]` | 允许执行的操作权限。 |

客户端传来的租户、用户或数据范围不会被信任；每次读取和写入都会以 JWT 中的已验证声明重新约束查询。

## 主要接口分类

| 分类 | 典型路径 | 说明 |
| --- | --- | --- |
| 登录与当前身份 | `/api/v1/auth/*` | 登录、修改密码、获取当前身份。 |
| 临床业务 | `/api/v1/patients`、`/api/v1/medical-records`、`/api/v1/prescriptions` | 受 JWT 与行级范围控制。 |
| 处方审批 | `/api/v1/workflows/prescription-status-changes/*` | 指定审批人完成处方状态变更。 |
| Agent 网关 | `/api/v1/agent/stream` | Java 鉴权后转发 Agent 的 SSE 流。 |
| 医学知识图谱 | `/api/v1/kg/*` | Java 鉴权后代理 Neo4j/Agent 查询。 |
| 知识治理 | `/api/v1/knowledge-documents`、`/api/v1/knowledge-index-versions` | 管理可发布医学知识与索引版本。 |
| 审计与通知 | `/api/v1/agent-audit/*`、`/api/v1/notifications/*` | 记录工具生命周期并向用户展示通知。 |

完整接口参数请以 Swagger 页面为准。

## 处方分析与审批

`GET /api/v1/analytics/prescriptions/schema` 与 `POST /api/v1/analytics/prescriptions/snapshot` 仅允许具有 `prescription:read` 权限的用户访问。后端会再次应用患者授权和行级范围，并移除患者姓名、诊断、药物、医生等可识别字段后才提供给 Agent。

处方状态变更不直接由模型完成：发起人提交请求后，Flowable 分配给指定审批人；只有审批通过后才会调用处方服务更新状态。

## 配置与生产部署

- 本地开发配置在 `application-dev.yml`；生产应通过环境变量提供数据库、Redis、JWT 与 Agent 地址。
- `JWT_SECRET`、数据库密码、Neo4j 密码和外部模型密钥必须由密钥管理系统或部署环境提供，不能写入仓库。
- `POST /api/v1/dev/token` 只在 `dev` profile 提供，生产 profile 不会注册该接口。
- `FLOWABLE_DATABASE_SCHEMA_UPDATE` 在生产默认关闭；Flowable 表升级应作为受控发布步骤执行。

## 验证

```powershell
Set-Location backend
mvn test
```

完整三端校验请从项目根目录运行 `./scripts/verify.ps1`。
