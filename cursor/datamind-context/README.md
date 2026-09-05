# DataMind Context Plugin (Cursor)

DataMind Context 是 DataMind 的 **Cursor 插件**。它让 Cursor Agent 可以使用你本地的资料文件夹，自动建立 RAG / GraphRAG 知识库，生成轻量 Markdown Wiki，并记住长期有价值的偏好、决策和工作流程。

如果你不熟悉 Profile、Session、RAG、GraphRAG 这些词，也可以直接使用。日常只需要会说几句话：

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹。
```

```text
用 DataMind 问：这批资料里最重要的结论是什么？
```

```text
用 DataMind 更新这个文件夹：/你的/资料/文件夹。
```

这版默认会自动处理 session 和 profile。你平时不用写 session，也通常不用自己起 profile 名字。

> Codex 用户请使用配套的 `datamind-context-plugin-0.8.1.zip`。两个版本共享 `vendor/datamind/` runtime 和 `~/.datamind-context/` 用户数据，可以无缝切换。

## 适合做什么

- 把本地资料文件夹变成可问答的知识库。
- 对文档、PDF、表格、Word、PPT 等资料做总结、比较、风险分析和行动建议。
- 用 GraphRAG 查询实体关系、多跳关系和资料之间的关联。
- 自动生成 Markdown Wiki，把资料库结构、来源页、问答和总结沉淀下来。
- 记住你的回答偏好、项目约定和常用工作流。
- 在不破坏 Markdown 记忆的前提下，用 MemOS-inspired 结构化记忆更精准地召回偏好和经验。

## 安装

### 方式 A: 从 GitHub Release 发布包一键安装（推荐）

发布包已经内置 DataMind 源码。通常不需要再单独 clone DataMind 主仓库。

```bash
unzip datamind-context-plugin-cursor-1.0.0.zip
cd datamind-context
./install.sh
```

如果之前已经安装过同名插件，并希望覆盖：

```bash
./install.sh --force
```

安装脚本会把插件复制到 `~/.cursor/plugins/local/datamind-context/`，使用包内的 `vendor/datamind` 作为 DataMind runtime，创建 `.venv` 并安装依赖。

如果你已经有自己的 DataMind 仓库，也可以显式指定：

```bash
./install.sh --repo-root /path/to/DataMind
```

### 方式 B: 从 DataMind 仓库源码安装

如果你已经 clone 了 DataMind 仓库，并希望用源码做开发安装：

```bash
cd /path/to/extracted/datamind-context
./install.sh --repo-root /path/to/DataMind
```

### 启用插件

完整退出并重启 Cursor，然后：

```text
Settings -> Plugins -> Local Plugins -> datamind-context (Enable)
```

更完整的安装、发布和隐私说明见 `INSTALL.md`。

> 安装后仍然需要编辑 DataMind 的 `.env`，填入你的 LLM 和 embedding API 配置。发布包不会内置任何 API key。

## 检查是否可用

在 Cursor Agent 里输入：

```text
用 DataMind 看一下现在有哪些 profile。
```

第一次没有 profile 是正常的。接下来可以使用一个资料文件夹：

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹。
```

## 先理解几个概念

如果你只是日常使用，可以先跳过这一节。真正要记住的是：DataMind 会帮你自动管理资料库名字和记忆流。

### Profile 是什么？

Profile 可以理解成一个“资料库名字”。

一个 profile 通常对应一个资料文件夹，例如：

```text
workdocs
projectdocs
customer-a
```

当你说：

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹。
```

如果没有指定 profile，DataMind 会自动创建一个，例如：

```text
xiangmu-ziliao
```

之后你可以直接问 DataMind。DataMind 会默认使用最近一次用过的 profile。

只有在你同时管理多个资料库时，才需要明确说：

```text
用 DataMind 问 workdocs：这个项目的关键风险是什么？
```

### Session 是什么？

Session 是“动态记忆流”。它记录你和 Cursor 互动中有长期价值的内容，比如：

- 回答格式偏好
- 常用工作流程
- 项目约定
- 资料处理规则
- 你反复强调的注意事项

默认 session 叫：

```text
global
```

平时你不用写 session。DataMind 会自动把高价值习惯写入 `global`。

只有当你想把不同工作完全隔离时，才需要自己指定 session。例如：

```text
用 DataMind 记住到 session paper-writing：以后论文相关回答先给审稿人视角。
```

### 结构化记忆是什么？

结构化记忆是 DataMind 在 Markdown 记忆之外新增的本地索引层，位置是：

```text
~/.datamind-context/memory.db
```

它会把长期有价值的信息拆成 memory item，例如 `preference`、`decision`、`workflow`、`summary`、`skill`、`feedback_hint`。日常不用手动管理它；DataMind 会自动写入并在查询时召回。

从 0.8.1 开始，DataMind 还会为每次 `datamind_ask` / `datamind_rag_query` / `datamind_graph_query` 留下一条轻量反馈轨迹。返回结果里的 `feedback_trace.id` 可以用于记录下一轮反馈；如果用户指出“不是这个”“需要改成……”“漏了……”，`datamind_record_feedback` 会把这次纠错转成 `feedback_hint`。

查询时，DataMind 会先带上 Wiki，再带上和问题相关的结构化记忆，最后带上旧的 session Markdown 记忆。

### Wiki 是什么？

Wiki 是 DataMind 为每个 profile 自动生成的 Markdown 知识层，位置在：

```text
~/.datamind-context/profiles/{profile}/wiki
```

里面包含 `index.md`、`sources/`、`questions/`、`syntheses/`、`user/preferences.md`、`log.md` 等结构。

### 原始文件夹和托管目录有什么区别？

原始文件夹是你的真实资料目录，DataMind 默认不会修改它。托管目录是 DataMind 自己维护的副本或抽取结果，位置是：

```text
~/.datamind-context/profiles/{profile}/data
```

RAG、GraphRAG 和 Wiki 都基于托管目录构建。

## 平时怎么说

完整的常用说法、强制重建、自动偏好捕获、记忆搜索、Wiki 健康检查等示例，请参见 `USAGE.md`。

## 数据位置

插件读取 DataMind 仓库根目录的 `.env` 配置。

插件运行数据在：

```text
~/.datamind-context/
  profiles/{profile}/data/
  profiles/{profile}/wiki/
  memory.db
  interactions/global/events.jsonl
  memories/
  skills/
```

这些是用户本地运行数据，不应提交到 GitHub 发布包。

## 工具列表

完整工具清单见 `USAGE.md` 和 `skills/datamind-context/SKILL.md`。

## 更多文档

```text
USAGE.md          # 新手使用教程
INSTALL.md        # 安装、验证、隐私和发布说明
RELEASE_NOTES.md  # 版本更新说明
```
