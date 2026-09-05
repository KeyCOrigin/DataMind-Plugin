# DataMind 企业双 MCP 插件

本项目采用本地企业双 MCP 架构：

```text
Codex / ChatGPT / 其他宿主
        |
        +--> 邮箱、飞书、外部数据库等独立 MCP
        |
        +--> datamind（Gateway MCP，对外）
                  |
                  +--> DataMind RetrieveAgent / StoreAgent
                                  |
                                  +--> DataPlane MCP（内部）
                                                |
                                                +--> KB / DB / Graph / Memory / Skills
```

Codex 只连接名为 `datamind` 的 Gateway。DataPlane 没有公网入口，也不使用 HTTP，
由 Gateway 作为本地子进程通过 stdio 启动，只供 DataMind 内部 Agent 使用。
RetrieveAgent 和 StoreAgent 仍然由 DataMind 主仓库构建，本仓库负责 MCP 服务
边界、本地工具提供器、入库协议和企业部署配置。

## Gateway 与 DataPlane 的区别

| 项目 | Gateway MCP | DataPlane MCP |
| --- | --- | --- |
| 使用者 | Codex、ChatGPT、Claude 等 MCP 宿主 | DataMind 的 RetrieveAgent、StoreAgent |
| 通信方式 | 本地 stdio，由 Codex 启动 `datamind-mcp` | 本地 stdio，由 Gateway 启动 DataPlane 子进程 |
| 主要职责 | 用户认证、租户和 profile、Agent 生命周期、外部入库任务、审计和回执 | KB、数据库、Graph、Memory、Skills 服务及底层存储 |
| 工具范围 | `datamind_agent_*`、外部入库、任务状态、profile 查询 | `kb_*`、`db_*`、`graph_*`、`memory_*`、`skill_*` |
| 数据库访问 | 不直接访问 DataMind 数据库 | 独占 DataMind 数据存储凭据 |
| 是否运行 LLM Agent | Gateway 内运行 DataMind Agent Runtime | 不运行 LLM Agent |

因此 Codex 无法发现或直接调用 DataPlane 底层工具。RetrieveAgent 只能获得读
工具，StoreAgent 只能获得完整的写工具目录。批量编排不会创建第二个 StoreAgent
或第二套写权限。

## 外部来源边界

邮箱、飞书、外部数据库和微信文章工具由 Codex 独立配置，不放入本插件，
DataMind 也不会获得这些平台的凭据。Codex 读取外部内容后，将其作为不可信
数据，经过确认后交给 Gateway。Gateway 只把来源、接口、格式清单和当前数据
分块交给同一个 StoreAgent；StoreAgent 自己决定调用 KB、DB 或 Graph 写工具。
它不能反向复用 Codex 的外部 MCP 会话，除非另行把外部凭据配置到 Gateway。

邮箱批量读取应使用邮箱 MCP 提供的批量工具，一次 IMAP 登录读取多个 UID，
再把结果分块交给 StoreAgent；不要让 Codex 对每封邮件重复建立 IMAP 会话。

旧的 `connector` 是进程内平台连接器抽象，已删除。旧的 `outbound` 是对外
发送、修改或删除路径，也已删除。本架构不提供任何外部发送、修改或删除能力。

## 仓库结构

```text
plugins/datamind-context/       Codex 插件清单、技能和本地 Gateway MCP 配置
services/gateway/               对外 stdio MCP 和 Agent Runtime
services/dataplane/             内部 DataMind 能力 MCP
packages/contracts/             Context、ExternalBatch、Receipt 和错误合同
packages/mcp-tool-provider/     本地 DataPlane ToolRegistry 适配器
deploy/helm/datamind-enterprise Kubernetes 部署、网络策略和探针
tests/                          合同与安全测试
scripts/                        校验与冒烟测试
```

## Gateway 对外工具

```text
datamind_agent_retrieve
datamind_agent_store
datamind_agent_status
datamind_external_source_status
datamind_external_ingest_submit
datamind_external_job_status
datamind_external_receipt_get
datamind_profile_list
datamind_profile_status
```

插件配置中不会暴露 `kb_*`、`db_*`、`graph_*`、`memory_*` 或 `skill_*`。

## 鉴权与隔离

本地 stdio 模式不经过 HTTP，也不依赖 OAuth 服务。Gateway 为每个本地进程生成
短期外部身份令牌；租户、用户和允许的 profile 由 `DATAMIND_LOCAL_TENANT`、
`DATAMIND_LOCAL_USER`、`DATAMIND_LOCAL_PROFILES` 环境变量提供。Gateway 仍然不
信任请求参数中未被允许的 profile。

Gateway 到 DataPlane 使用五分钟短期服务 JWT，生产环境同时启用 mTLS。
DataPlane 校验签发方、受众、服务名、过期时间、租户、profile、Agent 角色和
精确权限：

```text
RetrieveAgent       datamind.dataplane.read
StoreAgent（普通保存和批量分块） datamind.dataplane.write
管理任务            datamind.dataplane.admin
```

数据按租户和 profile 分区。Gateway 控制状态使用 PostgreSQL；DataPlane 独占
DataMind 的数据库、向量库、图存储、对象存储和 Embedding 凭据。

## Embedding 配置

Embedding 只在 DataPlane 配置。Helm 支持地址、供应商、模型、向量维度、批量
大小、超时和重试参数，API Key 从 Kubernetes Secret 读取。生产环境若缺少
Embedding 地址或密钥会拒绝启动，不会错误复用 Anthropic 的 LLM 地址。

示例：

```yaml
embedding:
  provider: openai_compatible
  apiBase: https://api.openai.com/v1
  model: text-embedding-3-small
  dimension: 1536
embeddingApiKeySecretKey: embedding-api-key
```

实际请求地址会规范为：`https://api.openai.com/v1/embeddings`。

## 外部入库流程

`datamind_external_ingest_submit` 是可选的批量编排入口，不是另一种入库 Agent。
它只负责校验 `ExternalBatch`、过滤敏感字段、计算内容哈希、幂等检查、分块进度、
回执和 checkpoint。每个分块都调用与 `datamind_agent_store` 相同的 StoreAgent，
StoreAgent 根据来源、接口和格式自主选择实际写工具；Gateway 不替它决定写 KB、DB
还是 Graph。

少量数据可以直接循环调用 `datamind_agent_store`，完全不需要批量入口。需要大批量、
失败重试或断点续跑时才使用 `datamind_external_ingest_submit`。批量入口不会把
全部数据一次性塞进 Agent 上下文，默认按 `DATAMIND_INGEST_BATCH_SIZE` 分块。

重复批次不会产生新增写入；checkpoint 冲突返回 `checkpoint_conflict`，不会
推进游标。

## 本地安装与启动

在 WSL 或 Linux 中执行：

```bash
cd /path/to/DataMind-Plugin
python3 -m venv .venv
.venv/bin/pip install -e packages/contracts -e packages/mcp-tool-provider \
  -e services/dataplane -e services/gateway \
  'plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl'
```

安装后会提供 `datamind-mcp` 命令。插件配置只引用这个命令，不包含源码绝对路径，
因此换用户、换目录或重新安装插件都不会失效。Codex 重启后，在 MCP 列表中应看到
`datamind`，而不会看到 `datamind-gateway` 或 DataPlane 底层工具。

本地数据目录解析顺序为：`DATAMIND_DATA_ROOT`、`XDG_DATA_HOME/datamind`、
`~/.local/share/datamind`。生产部署可通过环境变量改到持久卷。

DataMind Agent 使用的模型协议也通过环境变量配置。用 OpenAI Codex 做本地测试时，
无需安装 `anthropic`，先设置一个 OpenAI 兼容端点和测试密钥：

```bash
export DATAMIND__LLM__PROTOCOL=openai_chat_completions
export DATAMIND__LLM__API_BASE=https://api.openai.com/v1
export DATAMIND__LLM__API_KEY=你的测试密钥
export DATAMIND__LLM__MODEL=gpt-4o-mini
```

如果使用其他 OpenAI 兼容服务，只需替换 `DATAMIND__LLM__API_BASE`、模型名和密钥；
不需要修改 MCP 代码。只有把协议设为 `anthropic` 时才需要额外安装 `anthropic` 包。

Embedding 使用独立配置，不会复用 LLM 地址或密钥：

```bash
export DATAMIND__EMBEDDING__PROVIDER=openai
export DATAMIND__EMBEDDING__API_BASE=https://api.openai.com/v1
export DATAMIND__EMBEDDING__API_KEY=你的Embedding密钥
export DATAMIND__EMBEDDING__MODEL=text-embedding-3-small
```

## 容器部署说明

本基线不启用公网 Gateway、Ingress、Streamable HTTP 或 DataPlane HTTP Service。
Gateway 与 DataPlane 是两个独立 MCP 进程，由 Gateway 通过本地 stdin/stdout
启动 DataPlane。容器镜像的入口分别是 `datamind-mcp` 和
`datamind-dataplane-mcp`；Gateway 镜像同时安装 DataPlane，以便在同一个受控
运行单元中启动子进程。Helm 只部署这个受控工作负载，不创建 HTTP Service。

## 本地校验

```bash
python3 scripts/validate.py
PYTHONPATH=packages/contracts/src:packages/mcp-tool-provider/src:services/gateway/src:services/dataplane/src \
  pytest -q tests
PYTHONPATH=packages/contracts/src:packages/mcp-tool-provider/src:services/gateway/src:services/dataplane/src \
  python3 scripts/smoke-test.py
```

当前校验覆盖仓库结构、Python 语法、Gateway 对外工具目录、权限边界和
ExternalBatch 合同。正式验收还需要接入真实企业 IdP、PostgreSQL、任务队列、
Embedding 服务、mTLS 和 Kubernetes NetworkPolicy。
