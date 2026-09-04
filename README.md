# DataMind 企业双 MCP 插件

本项目采用企业双 MCP 架构：

```text
Codex / ChatGPT / 其他宿主
        |
        +--> 邮箱、飞书、外部数据库等独立 MCP
        |
        +--> Gateway MCP（对外）
                  |
                  +--> DataMind RetrieveAgent / StoreAgent
                                  |
                                  +--> DataPlane MCP（内部）
                                                |
                                                +--> KB / DB / Graph / Memory / Skills
```

宿主只连接 Gateway。DataPlane 没有公网入口，只供 DataMind 内部 Agent 使用。
RetrieveAgent 和 StoreAgent 仍然由 DataMind 主仓库构建，本仓库负责 MCP 服务
边界、远程工具提供器、入库协议和企业部署配置。

## Gateway 与 DataPlane 的区别

| 项目 | Gateway MCP | DataPlane MCP |
| --- | --- | --- |
| 使用者 | Codex、ChatGPT、Claude 等 MCP 宿主 | DataMind 的 RetrieveAgent、StoreAgent |
| 网络位置 | 企业网络或公网 HTTPS | Kubernetes 集群内部 `ClusterIP` |
| 主要职责 | 用户认证、租户和 profile、Agent 生命周期、外部入库任务、审计和回执 | KB、数据库、Graph、Memory、Skills 服务及底层存储 |
| 工具范围 | `datamind_agent_*`、外部入库、任务状态、profile 查询 | `kb_*`、`db_*`、`graph_*`、`memory_*`、`skill_*` |
| 数据库访问 | 不直接访问 DataMind 数据库 | 独占 DataMind 数据存储凭据 |
| 是否运行 LLM Agent | Gateway 内运行 DataMind Agent Runtime | 不运行 LLM Agent |

因此 Codex 无法发现或直接调用 DataPlane 底层工具。RetrieveAgent 只能获得读
工具，StoreAgent 只能获得写工具，外部入库只能获得更窄的追加写权限。

## 外部来源边界

邮箱、飞书、外部数据库和微信文章工具由 Codex 独立配置，不放入本插件，
DataMind 也不会获得这些平台的凭据。Codex 读取外部内容后，将其作为不可信
数据，经过确认后以 `ExternalBatch` 提交给 Gateway。

旧的 `connector` 是进程内平台连接器抽象，已删除。旧的 `outbound` 是对外
发送、修改或删除路径，也已删除。本架构不提供任何外部发送、修改或删除能力。

## 仓库结构

```text
plugins/datamind-context/       Codex 插件清单、技能和 Gateway MCP 配置
services/gateway/               对外 Streamable HTTP MCP 和 Agent Runtime
services/dataplane/             内部 DataMind 能力 MCP
packages/contracts/             Context、ExternalBatch、Receipt 和错误合同
packages/mcp-tool-provider/     远程 DataPlane ToolRegistry 适配器
deploy/helm/datamind-enterprise Kubernetes 部署、网络策略和探针
tests/                          合同与安全测试
scripts/                        校验与冒烟测试
```

## Gateway 对外工具

```text
datamind_agent_retrieve
datamind_agent_store
datamind_agent_store_external
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

Codex 到 Gateway 使用 OAuth 2.1/OIDC。身份令牌提供租户、用户、允许使用的
profile，以及 `datamind:retrieve` 和 `datamind:store` 权限。Gateway 不信任
请求参数中任意指定的 profile。

Gateway 到 DataPlane 使用五分钟短期服务 JWT，生产环境同时启用 mTLS。
DataPlane 校验签发方、受众、服务名、过期时间、租户、profile、Agent 角色和
精确权限：

```text
RetrieveAgent       datamind.dataplane.read
StoreAgent          datamind.dataplane.write
外部入库            datamind.dataplane.external_write
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

`datamind_external_ingest_submit` 会校验 `ExternalBatch`、过滤敏感字段、计算
内容哈希、执行幂等检查并返回 `job_id`。异步任务调用 StoreAgent，保存
DataPlane 回执，只有所有回执成功后才通过乐观锁提交 checkpoint。

重复批次不会产生新增写入；checkpoint 冲突返回 `checkpoint_conflict`，不会
推进游标。

## 部署

```bash
helm upgrade --install datamind deploy/helm/datamind-enterprise \
  --set ingress.enabled=true \
  --set embedding.apiBase=https://api.openai.com/v1
```

Helm 提供独立的 Gateway 和 DataPlane Deployment、DataPlane 内部 Service、
NetworkPolicy、非 root 容器、只读根文件系统、启动/就绪/存活探针、持久卷、
HPA 和 PDB。生产环境启用 `mtls.enabled`，并提供对应证书 Secret。

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
