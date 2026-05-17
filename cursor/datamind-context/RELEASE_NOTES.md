# DataMind Context Plugin (Cursor) 1.0.0

## 1.0.0 (Cursor) 发布重点

DataMind Context 1.0.0 是首个稳定版本。三家插件（Codex / Claude Code / Cursor）现在统一在 `OpenDCAI/DataMind-Plugin` 仓库下，三个独立子目录，均可单独 `git clone` 安装。

Cursor 子目录的关键设计：

- 通过 Cursor 0.46+ 的 Local Plugins 机制（`~/.cursor/plugins/local/*`）自动发现，配合 `mcp.json` 注册 MCP server；不需要手写 `~/.cursor/mcp.json`。
- 因为 Cursor 不会读取插件目录里的 `SKILL.md`，新增等价的 **Cursor Rule**（`.cursor/rules/datamind.mdc`）。`install.sh` 会把它复制到 `~/.cursor/rules/datamind.mdc`，让 Agent 在任何工程下看到"知识库 / RAG / 记忆 / 偏好"等关键词时自动调 `datamind_*` 工具。
- 与 Codex / Claude Code 共享同一份 `vendor/datamind/` runtime、同一套 17-tool MCP server 和同一个 `~/.datamind-context/` 用户数据目录——三个 IDE 间的 profile / Wiki / 记忆完全互通。
- MCP server 版本号同步升至 `1.0.0`。

### 安装

```bash
unzip datamind-context-plugin-cursor-1.0.0.zip
cd datamind-context
./install.sh
```

完整退出并重启 Cursor，然后在 `Settings -> Plugins -> Local Plugins` 启用 `datamind-context`。

---

# DataMind Context Plugin (Cursor) 0.8.1

## 0.8.1 (Cursor) 发布重点

这是 DataMind Context 插件第一个面向 **Cursor IDE** 的发布版本，与同版本 Codex 插件功能一致，仅在打包层做了适配。

### 与 Codex 版本的对照

| 维度 | Codex 版本 | Cursor 版本 |
|---|---|---|
| 清单 | `.codex-plugin/plugin.json` | `.cursor-plugin/plugin.json` |
| MCP 配置 | `.mcp.json` | `mcp.json`（Cursor 自动从插件根目录发现）|
| 安装目录 | `~/plugins/datamind-context/` | `~/.cursor/plugins/local/datamind-context/` |
| Marketplace | `~/.agents/plugins/marketplace.json` | Cursor 自动发现 `~/.cursor/plugins/local/*` |
| 启用位置 | Codex 插件列表 | `Settings -> Plugins -> Local Plugins` |
| Skill | `skills/datamind-context/SKILL.md`（agentskills.io 格式）| 同左，零修改 |
| Runtime | `vendor/datamind/` | 同左，零修改 |
| MCP server | `src/datamind_mcp.py`（stdio）| 同左，零修改 |
| 用户数据 | `~/.datamind-context/` | 同左 |

也就是说，已经在 Codex 上用过 DataMind 的用户，可以直接安装 Cursor 版本，不会丢失任何 profile、Wiki 或结构化记忆——两个 IDE 共享同一份 `~/.datamind-context/` 数据目录。

### 与 0.8.1 (Codex) 同步的能力

- `datamind_ask` / `datamind_rag_query` / `datamind_graph_query` 为每次回答返回 `feedback_trace.id`。
- `datamind_record_feedback` 可记录后续用户确认、纠错、重试或下一状态信号。
- 负反馈会自动沉淀为 `feedback_hint` 结构化记忆，后续相似问题会通过原有 query context 机制被召回。
- `datamind_feedback_status` 可查看反馈轨迹、反馈事件、待反馈 trace 数量和近期纠错。
- `memory.db` 包含反馈轨迹和反馈事件表；旧的 Markdown / Wiki / 结构化记忆行为保持兼容。

### 安装

```bash
unzip datamind-context-plugin-cursor-1.0.0.zip
cd datamind-context
./install.sh
```

完整退出并重启 Cursor，然后在 `Settings -> Plugins -> Local Plugins` 启用 `datamind-context`。

### 隐私说明

发布包只包含插件代码、文档和干净的 DataMind runtime 源码，不包含用户运行数据。

不应包含:

- `~/.datamind-context/`
- `memory.db`
- `profiles.json`
- `profiles/{profile}/`
- `interactions/{session}/events.jsonl`
- `memories/{session}/memory.md`
- `skills/{session}/*.md`
- `.datamind-repo-root`
- `.env`
- `.venv`
- `storage/`

安装时插件会在用户自己的机器上创建 `.datamind-repo-root`，其中只记录用户本地 DataMind runtime 路径。
