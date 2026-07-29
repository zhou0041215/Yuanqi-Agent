# 安全与全链路验收矩阵

## 自动化覆盖

| 边界 | 攻击或失败模式 | 预期防线 | 自动化验证 |
|---|---|---|---|
| Java JWT | 错误 issuer/audience、非正数身份 claim | 401，不能建立用户上下文 | `JwtValidationTest` |
| Java 数据层 | 越部门、越 owner 或未授权患者读取或修改 | repository 查询重新施加行级范围 | Java security integration tests |
| Java 关系 | 绑定不存在的患者或人员 | service 校验 + 外键 | business-domain integration tests |
| Java 写入 | 同一操作重试 | `Idempotency-Key` 缓存并复用结果 | idempotency integration tests |
| Flowable | 自批、非受让人审批、未批先改 | 请求人与审批人分离；task assignee 过滤；批准分支才调用行级 Service | Flowable workflow integration test |
| 分析快照 | 伪造部门、超范围日期、超量数据 | 复用行级 Specification；366 天/10,000 行上限 | analytics snapshot integration test |
| Agent 工具 | 模型选择无权限工具或构造额外字段 | 权限过滤目录 + Pydantic `extra=forbid` 二次校验 | planner/tool tests |
| HITL | 未审批写入、换用户恢复、篡改参数 | `interrupt()`；fresh JWT；身份绑定；参数 fingerprint | graph HITL tests |
| Checkpoint | JWT 泄漏到持久状态 | token 仅存在 request runtime，不进入 AgentState | graph HITL tests |
| Java 回调 | 任意 URL/SSRF、大响应 | 固定 base URL + `/api/v1/` allowlist + 响应上限 | Java client tests |
| AST | `os`/`subprocess`/文件 I/O/eval/dunder/复杂度逃逸 | 静态拒绝，未进入物理沙箱 | AST policy tests |
| Docker | 沙箱访问公网或宿主文件、资源耗尽 | `--network none`、read-only、non-root、cap-drop、PID/CPU/memory/time limit | Docker command tests + opt-in runtime tests |
| GraphRAG | Cypher 注入、越过医学知识治理规则的图路径或向量命中 | 固定参数化 Cypher；治理规则过滤与返回后复核 | retrieval tests |
| SSE | UTF-8/JSON 被网络分片、超大事件 | Buffer 重组、严格事件校验、1 MiB 上限 | frontend SSE tests |
| 图表 | formatter 函数、`__proto__` 或未知配置注入 | ECharts option 白名单清理 | frontend chart tests |

## 发布前人工红队

1. 使用 SELF、DEPARTMENT、ALL 三种 scope 请求已知资源 ID，确认不能越过科室、本人或患者授权边界。
2. 让规划模型返回未展示给它的写工具、额外参数、负数 ID、超长代码和未知工具名。
3. 在审批挂起后使原 JWT 过期，再分别使用同用户新 JWT 和另一用户 JWT 恢复。
4. 尝试 `__subclasses__`、动态 import、反射、Pandas 文件/网络读取、压缩炸弹式输出和无限循环。
5. 在沙箱内解析 DNS、连接公网 IP、读取宿主路径、创建过量进程，并观察超时及资源限制。
6. 向 Neo4j/Qdrant 植入已退役或被治理规则排除的同关键词文档，确认检索结果与日志均不包含其内容。
7. 通过逐字节、CRLF、多行 data、断流、非法 JSON、超限 payload 回放 SSE；向图表字段注入脚本/函数文本。
8. 对写请求进行网络重放，确认 `Idempotency-Key` 相同不产生重复业务记录。

## 本地真实链路冒烟

在隔离的开发数据源中启动 Java、Agent 与基础设施后执行：

```powershell
.\scripts\live-smoke.ps1 -ExpectGraphRag
```

该脚本使用真实 HTTP、MySQL、Redis、Neo4j、Qdrant、Flowable 和 Docker 沙箱，覆盖 Java 认证网关、SSE、去标识化处方 Text-to-Pandas、混合检索、LangGraph 写工具中断/驳回、Agent 审计，以及独立审批人完成处方状态 Flowable 流程。脚本只写入带 `SMOKE-` 唯一前缀的开发患者和处方记录。

## 生产门禁

- 禁止启用 `dev` Spring profile；JWT secret、数据库、Neo4j、Qdrant 与模型网关凭据进入 secret manager。
- Java 与 Agent 仅走受控内网；前端通过同源网关访问；启用 TLS、限流、审计日志和 trace ID 关联。
- GraphRAG 索引任务必须是受信离线作业，并在入库前写入数据分级标签。
- 不要为方便部署而把宿主 Docker socket 直接挂给公网可达的 Agent 容器；生产沙箱应使用专用 worker/节点和独立运行时策略。
