# YuanQi 前端说明

`frontend/` 是 React 18 + TypeScript + Ant Design X 应用，提供登录、医学问答、知识图谱、患者工作台、知识治理、审批审计和通知界面。

前端只负责展示与交互：它不保存业务规则，也不直接访问 MySQL、Neo4j 或 FastAPI Agent。开发环境下，Vite 会把所有 `/api/v1/*` 请求转发给 Java 后端；Java 完成 JWT 校验后才会访问 Agent。

## 本地运行

请先启动 Java 后端，再执行：

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

本地演示账号：

| 用户名 | 初始密码 | 说明 |
| --- | --- | --- |
| `yu_ming_demo` | `123456` | 首次登录必须改密码。仅用于本地开发。 |

## 前端如何访问后端？

默认不需要额外配置。`vite.config.ts` 中已将 `/api/v1` 代理到 `http://127.0.0.1:8080`。

部署到同源网关时，保持 `VITE_AGENT_API_BASE_URL` 为空即可；如果网关为 Agent 路由提供了额外前缀，可在 `.env` 中设置该变量，例如：

```dotenv
VITE_AGENT_API_BASE_URL=/agent-api
```

`.env` 仅用于本机或部署环境，不能提交到 GitHub。

## SSE 与动态界面

Agent 的 SSE 响应会被前端按完整事件帧缓冲后解析，避免网络分片导致中文乱码或 JSON 截断。支持的事件类型：

| 事件 | 界面行为 |
| --- | --- |
| `reasoning` | 展示简短、公开的执行进度。 |
| `text` | 增量渲染 Markdown 回答。 |
| `uiData` | 渲染受白名单约束的图表或审批卡片。 |
| `done` | 标记当前回答完成。 |
| `error` | 显示可理解的失败信息。 |

审批卡片只会提交“批准/驳回”决定；权限复核和实际写入始终在 Agent 与 Java 后端完成。

## 医学知识图谱

知识图谱页面依赖 Java 网关和 Neo4j。仓库不包含完整医学目录数据，因此刚克隆项目时图谱可能没有完整疾病内容；请按根目录 README 的“导入医学知识图谱”说明，在本机导入合法数据后使用。

## 验证与构建

```powershell
npm test
npm run build
```

测试覆盖 SSE 分片重组、UTF-8、多行事件、超限保护、图表配置清理和知识图谱组件行为。
