# DataMind Context Plugin 1.0.0

## 1.0.0 发布重点

DataMind Context 1.0.0 是首个稳定版本，重点是把 Codex / Claude Code / Cursor 三家插件统一到同一个 GitHub 仓库（`OpenDCAI/DataMind-Plugin`）下，分别承载完整、独立、可单独 `git clone` 安装的发布副本。

- 三家共享同一份 `vendor/datamind/` runtime 和同一套 17-tool MCP server (`src/datamind_mcp.py`)，运行时数据都在 `~/.datamind-context/` 下，可以无缝切换 IDE。
- Codex 子目录沿用原 `~/plugins/datamind-context/` + `~/.agents/plugins/marketplace.json` 安装路径。
- Claude Code 子目录通过 `claude plugin marketplace add` + `claude plugin install` 一键集成；附带 SessionStart 钩子按需建立 venv，支持复用 Codex 已有 venv。
- Cursor 子目录走 `~/.cursor/plugins/local/` 自动发现，并把等价的 Cursor Rule 复制到 `~/.cursor/rules/datamind.mdc`，让 Agent 看到"知识库 / RAG / 记忆"等关键词时主动调 `datamind_*`。
- 仓库根附 `scripts/sync-core.sh`，以 codex 版为权威，自动同步 `src/*.py`、`vendor/datamind/`、`assets/` 到另两家。
- MCP server 版本号同步升至 `1.0.0`。

# DataMind Context Plugin 0.8.1

## 0.8.1 发布重点

这个版本引入 OpenClaw-RL 启发的轻量 next-state feedback 闭环，但不引入 GPU 训练或模型微调依赖。

- `datamind_ask` / `datamind_rag_query` / `datamind_graph_query` 现在会为每次回答返回 `feedback_trace.id`。
- 新增 `datamind_record_feedback`，可记录后续用户确认、纠错、重试或下一状态信号。
- 负反馈会自动沉淀为 `feedback_hint` 结构化记忆，后续相似问题会通过原有 query context 机制被召回。
- 新增 `datamind_feedback_status`，用于查看反馈轨迹、反馈事件、待反馈 trace 数量和近期纠错。
- `memory.db` 新增反馈轨迹和反馈事件表；旧的 Markdown/Wiki/结构化记忆行为保持兼容。

# DataMind Context Plugin 0.8.0

## 发布重点

这个版本面向 Codex 本地插件发布，重点是把 DataMind 的资料库问答、GraphRAG、Markdown Wiki、动态记忆和 MemOS-inspired 结构化记忆整理成一个可分发插件包。

从 0.8.0 开始，release 包可以内置干净的 DataMind runtime 源码:

```text
vendor/datamind/
```

这意味着普通用户可以只下载 `datamind-context-plugin` 发布包，运行 `./install.sh`，不需要先单独 clone DataMind 主仓库。安装脚本会自动创建 `.venv` 并安装依赖。用户仍需自己填写 `.env` 中的 LLM 和 embedding API 配置。

发布包入口 `README.md` 已包含完整新手使用教程，解释 Profile、Session、Wiki、结构化记忆、原始文件夹和托管目录等概念；不熟悉 DataMind 的用户可以从 README 直接开始，不需要先理解内部工具名。

## 新增能力

- 支持 release 包内置 DataMind runtime，降低安装门槛。
- `install.sh` 的 `--repo-root` 改为可选；如果包内存在 `vendor/datamind/`，默认使用内置 runtime。
- `install.sh` 会自动创建 `.venv`、安装依赖，并在缺少 `.env` 时从 `.env.example` 创建模板。
- 支持 `--skip-deps` 跳过依赖安装，支持 `--python PATH` 指定 Python。
- 新增结构化记忆索引 `~/.datamind-context/memory.db`。
- 新增 `datamind_search_memory`，可直接搜索结构化记忆。
- `datamind_remember` 会继续写入旧的 Markdown/Wiki 路径，同时写入结构化记忆。
- `datamind_save_memory` / `datamind_consolidate_memory` 会继续生成 `memory.md` 和 `skill.md`，同时索引 summary 和 skill。
- `datamind_ask` / `datamind_rag_query` / `datamind_graph_query` 会在查询上下文中加入相关结构化记忆。
- `datamind_list_memories` 会返回结构化记忆统计。

## 保持兼容

- 已有 DataMind 仓库用户仍可通过 `./install.sh --repo-root /path/to/DataMind` 使用外部仓库。
- `DATAMIND_REPO_ROOT` 环境变量仍可覆盖 runtime 路径。
- 不迁移、不删除旧的 `events.jsonl`、`memory.md`、`skill.md` 或 Wiki 文件。
- 如果 SQLite FTS 不可用，会退回 LIKE 搜索。
- 如果结构化记忆库不存在或检索失败，会退回原来的 Wiki + Markdown memory 行为。
- 原始资料文件夹仍默认只读，插件先抽取到托管目录再建索引。

## 适合用户

- 希望一键安装 Codex 插件后直接使用 DataMind 的用户。
- 希望 Codex 能用本地资料夹做 RAG / GraphRAG 问答的用户。
- 希望资料库有可读 Markdown Wiki 的用户。
- 希望 Codex 能记住偏好、决策、项目约定和可复用 workflow 的用户。
- 希望长期记忆既能被人审阅，也能被机器精准召回的用户。

## 隐私说明

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
