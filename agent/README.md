# YuanQi Agent 说明

`agent/` 是 FastAPI + LangGraph 编排服务。它负责医学知识图谱检索、自然语言回答、报告解读、工具调用和人工审批中断；它**不直接连接 MySQL**，也不会把 JWT 写入 checkpoint。

## 请求如何流转？

1. 浏览器请求先进入 Java 后端，Java 验证 JWT。
2. Java 将当前 JWT 与请求转发到 Agent；Agent 再调用 Java 的 `/api/v1/auth/context` 确认用户、租户、科室和权限。
3. 读工具可以立即执行；写工具把待执行参数和指纹写入 LangGraph checkpoint 后调用 `interrupt()` 暂停。
4. 用户在前端批准或驳回后，新的请求携带新的 JWT 恢复流程；恢复时会再次验证身份与权限。
5. Agent 将 `reasoning`、`text`、`uiData`、`done` 或 `error` 按 SSE 事件流返回。

## 对外接口

Agent 应仅部署在 Java 后端可访问的内网，浏览器不要直接访问它。

| 接口 | 用途 |
| --- | --- |
| `POST /api/v1/agent/stream` | 启动一次对话或工具调用，流式返回 SSE。 |
| `POST /api/v1/agent/threads/{threadId}/resume/stream` | 对等待审批的写操作执行批准/驳回并流式返回结果。 |
| `GET /api/v1/agent/tools` | 返回当前身份有权使用的工具定义。 |
| `GET /api/v1/kg/*` | 提供医学知识图谱搜索、科室、概览和关系图数据。 |
| `POST /api/v1/medical-reports/analyze` | 在内存中解析 PDF、TXT、CSV、JPG、PNG 报告，不保存原文件。 |

## 本地运行

先在项目根目录启动 MySQL、Redis、Neo4j，并启动 Java 后端；Agent 需要通过 Java 校验调用方身份。

```powershell
Set-Location agent
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\yuanqi-agent
```

默认监听 `http://localhost:8000`。`agent/.env` 是本机文件，不应提交到 GitHub。模板中的 Neo4j 与 Qdrant 端口已经和根目录 Docker 模板保持一致；如自行修改 Docker 映射端口，也要同步修改这里。

## 重要环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `YUANQI_JAVA_BASE_URL` | `http://localhost:8080` | Java 后端地址。 |
| `YUANQI_CHECKPOINT_DB_PATH` | `./data/checkpoints.sqlite` | 本地 LangGraph 状态库；含会话状态，禁止提交。 |
| `YUANQI_PLANNER_OLLAMA_URL` | 空 | 本地 Ollama 工具调用地址，可选。 |
| `YUANQI_PLANNER_API_URL` | 空 | 内网规划模型网关地址；优先于 Ollama。 |
| `YUANQI_GRAPHRAG_ENABLED` | `false` | 设为 `true` 时启用 Neo4j + Qdrant 混合检索。 |
| `YUANQI_NEO4J_*` | 本地 Docker 默认值 | Neo4j 连接信息。 |
| `YUANQI_QDRANT_*` | 本地 Docker 默认值 | 启用 GraphRAG 时使用的向量库信息。 |

模型规划器只接收用户问题和当前权限允许的工具 Schema；JWT 与 Java 返回的身份上下文不会发送给模型。

## 医学知识数据与 GraphRAG

项目仓库不包含完整医学目录文件 `agent/data/medical.json`。这是为了避免把大体量、来源治理状态不同的数据与源码混在一起。下载者可以先运行业务界面；如要构建完整本地图谱，请自行确认数据来源合法且不含个人信息后执行：

```powershell
Set-Location agent
.\.venv\Scripts\python scripts/import_disease_kb.py --file data/medical.json
.\.venv\Scripts\python scripts/standardize_medical_catalog.py
.\.venv\Scripts\python scripts/publish_trusted_medical_subset.py
```

开启 GraphRAG 时，还需要启动 Qdrant，设置 `YUANQI_GRAPHRAG_ENABLED=true`，并运行 `scripts/index_medical_knowledge.py`，或直接运行 `scripts/run_medical_pipeline.ps1`。数据可信等级、来源和药物展示限制见 [可信医学问答与知识发布](../docs/TRUSTED_MEDICAL_QA.md)。

## 报告解析与隔离计算

- 支持最大 10 MB 的 PDF、TXT、CSV、JPG、PNG 文件。
- PDF 必须包含可复制文本；图片 OCR 需安装 `.[dev,report-ocr]`、Tesseract 5 和 `chi_sim` 中文语言包。
- 文件只在内存中解析，默认不持久化。系统只提取明确的原文项目和异常标记，不自行推断参考范围。
- 处方分析会在无网络、只读根文件系统、非 root、限时限内存的 Docker 沙箱中执行；先经过 AST 安全规则检查。

构建沙箱镜像：

```powershell
docker build -f sandbox/Dockerfile -t yuanqi-agent-sandbox:local sandbox
```

## 测试

```powershell
Set-Location agent
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m pytest
```

需要真实 Docker 沙箱的测试：

```powershell
$env:YUANQI_RUN_DOCKER_TESTS = "1"
.\.venv\Scripts\python -m pytest tests/test_docker_runtime.py
```
