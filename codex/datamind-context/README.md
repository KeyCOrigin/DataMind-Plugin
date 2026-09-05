# DataMind Context Plugin

DataMind Context 是 DataMind 的 Codex 插件。它让 Codex 可以使用你本地的资料文件夹，自动建立 RAG / GraphRAG 知识库，生成轻量 Markdown Wiki，并记住长期有价值的偏好、决策和工作流程。

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

## 适合做什么

- 把本地资料文件夹变成可问答的知识库。
- 对文档、PDF、表格、Word、PPT 等资料做总结、比较、风险分析和行动建议。
- 用 GraphRAG 查询实体关系、多跳关系和资料之间的关联。
- 自动生成 Markdown Wiki，把资料库结构、来源页、问答和总结沉淀下来。
- 记住你的回答偏好、项目约定和常用工作流。
- 在不破坏 Markdown 记忆的前提下，用 MemOS-inspired 结构化记忆更精准地召回偏好和经验。

## 安装

### 方式 A: 从 DataMind 仓库安装

如果插件位于 DataMind 仓库内的 `plugins/datamind-context/`，从仓库根目录运行：

```bash
cd /path/to/DataMind
./scripts/install_codex_plugin.sh
```

然后重启 Codex，在插件/工具入口启用：

```text
DataMind Context
```

### 方式 B: 从 GitHub Release 发布包一键安装

如果你下载的是独立发布包，发布包已经内置 DataMind 源码。通常不需要再单独 clone DataMind 主仓库。

先解压，然后运行：

```bash
unzip datamind-context-plugin-codex-1.0.0.zip
cd datamind-context
./install.sh
```

如果之前已经安装过同名插件，并希望覆盖：

```bash
./install.sh --force
```

安装脚本会把插件复制到 `~/.codex/marketplaces/datamind/plugins/datamind-context`，使用包内的 `vendor/datamind` 作为 DataMind runtime，创建 `.venv` 并安装依赖。

如果你已经有自己的 DataMind 仓库，也可以显式指定：

```bash
./install.sh --repo-root /path/to/DataMind
```

然后重启 Codex，在插件/工具入口启用：

```text
DataMind Context
```

更完整的安装、发布和隐私说明见：

```text
INSTALL.md
```

安装后仍然需要编辑 DataMind 的 `.env`，填入你的 LLM 和 embedding API 配置。发布包不会内置任何 API key。

## 检查是否可用

在 Codex 里输入：

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

也就是说，`DataFlow-PPT` 这样的文件夹默认会生成 `dataflow-ppt`，不会再追加 hash 后缀。

之后你可以直接问 DataMind。DataMind 会默认使用最近一次用过的 profile。

只有在你同时管理多个资料库时，才需要明确说：

```text
用 DataMind 问 workdocs：这个项目的关键风险是什么？
```

### Session 是什么？

Session 是“动态记忆流”。

它记录你和 Codex 互动中有长期价值的内容，比如：

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

它会把长期有价值的信息拆成 memory item，例如：

- `preference`：你的回答偏好和习惯。
- `decision`：项目中的稳定决策。
- `workflow`：可复用工作流程。
- `summary`：阶段性总结。
- `skill`：沉淀出来的可复用 skill。
- `feedback_hint`：从用户纠错或下一轮反馈中提炼出的改进提示。

日常不用手动管理它。你继续用原来的说法，DataMind 会自动写入并在查询时召回。

从 0.8.1 开始，DataMind 还会为每次 `datamind_ask` / `datamind_rag_query` / `datamind_graph_query` 留下一条轻量反馈轨迹。返回结果里的 `feedback_trace.id` 可以用于记录下一轮反馈；如果用户指出“不是这个”“需要改成……”“漏了……”，`datamind_record_feedback` 会把这次纠错转成 `feedback_hint`，之后相似问题会自动带上这条经验。

查询时，DataMind 会优先带上 Wiki，再带上和问题相关的结构化记忆，最后带上旧的 session Markdown 记忆：

```text
Wiki
结构化记忆
Markdown session memory
```

如果结构化数据库不可用，DataMind 会自动退回旧的 Wiki + Markdown 记忆路径。

### Wiki 是什么？

Wiki 是 DataMind 为每个 profile 自动生成的 Markdown 知识层。

它不是替代 RAG，而是在 RAG / GraphRAG 上面多一层可读、可累积的结构化知识：

```text
原始文件夹
  -> 托管抽取目录
  -> RAG / GraphRAG 索引
  -> Markdown Wiki
  -> Codex 查询和操作
```

Wiki 里会有：

```text
index.md              资料库总览
sources/              每个来源文件的来源页
questions/            自动沉淀的高价值问题
syntheses/            可复用的回答总结和分析
user/preferences.md   和这个资料库相关的用户偏好
log.md                Wiki 更新日志
schema.md             Wiki 结构说明
```

位置在：

```text
~/.datamind-context/profiles/{profile}/wiki
```

### 原始文件夹和托管目录有什么区别？

原始文件夹是你的真实资料目录，DataMind 默认不会修改它。

托管目录是 DataMind 自己维护的副本或抽取结果，位置是：

```text
~/.datamind-context/profiles/{profile}/data
```

RAG、GraphRAG 和 Wiki 都基于托管目录构建。

## 平时怎么说

### 1. 使用一个资料文件夹

最省心：

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹。
```

如果你想自己起名字：

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹，profile 叫 workdocs。
```

不写 profile 时，DataMind 会自动创建一个 profile，并告诉你名字。

### 2. 直接问

```text
用 DataMind 问：这批资料里最重要的结论是什么？
```

如果你刚刚使用过一个文件夹，DataMind 会默认使用最近那个 profile。

如果你想指定资料库：

```text
用 DataMind 问 workdocs：这批资料里最重要的结论是什么？
```

总结、方案、风险、比较、决策这类高价值问答会自动沉淀到 Wiki：

```text
~/.datamind-context/profiles/{profile}/wiki/questions/
~/.datamind-context/profiles/{profile}/wiki/syntheses/
```

### 3. 文件夹变了就刷新

```text
用 DataMind 更新这个文件夹：/你的/资料/文件夹。
```

或者：

```text
用 DataMind 更新 workdocs。
```

默认更新会先做增量探测：

- 用文件 SHA1 对比上次 manifest。
- 跳过没有变化的文件。
- 忽略 Office 生成的 `~$` 临时锁文件。
- 如果没有新增、修改、删除任何会进入索引的文件，就跳过 RAG / GraphRAG 重建。
- 如果发现索引相关文件变化，当前版本会自动触发一次完整索引重建，避免向量库出现重复或陈旧内容。

如果你确实想强制全量重建，可以明确说：

```text
用 DataMind 强制重建 workdocs。
```

### 4. 偏好会自动记

你不用说 session。

当你说出稳定偏好、工作习惯、资料处理规则时，Codex 会自动记到全局 session：

```text
以后总结资料时，先给结论，再给证据。
```

```text
以后处理资料文件夹时，不要修改原始文件。
```

```text
这类项目默认输出中文，保留关键英文术语。
```

这些会进入默认全局 session：

```text
global
```

同时也会被索引到结构化记忆库：

```text
~/.datamind-context/memory.db
```

后续你问相关问题时，DataMind 会按问题内容自动召回这些偏好，不再只依赖整篇 `memory.md`。

### 5. 搜索已经记住的内容

如果你想直接查 DataMind 记住了什么，可以这样说：

```text
用 DataMind 搜索记忆：资料总结的输出格式偏好。
```

也可以指定资料库：

```text
用 DataMind 在 workdocs 的记忆里搜索：项目风险评估流程。
```

这会调用结构化记忆检索，不会修改任何记忆文件。

### 6. 检查 Wiki 是否健康

```text
用 DataMind 检查这个资料库的 Wiki。
```

DataMind 会检查必要页面、坏链接、没有被索引引用的来源页，以及有问题但缺少 synthesis 的沉淀项。

检查报告会写到：

```text
~/.datamind-context/profiles/{profile}/wiki/lint.md
```

## 一个完整例子

```text
用 DataMind 使用这个文件夹：/Users/you/Documents/项目资料。
```

DataMind 会自动创建 profile，例如：

```text
xiangmu-ziliao
```

然后直接问：

```text
用 DataMind 问：请总结这批资料的关键结论和下一步行动。
```

这条问答如果被判断为有长期价值，会自动保存到：

```text
~/.datamind-context/profiles/{profile}/wiki/syntheses/
```

再告诉 Codex 你的偏好：

```text
以后这类总结先给行动建议，再给背景解释。
```

以后继续问时，不需要再写 session。

你也可以查看它自动生成的 Wiki：

```text
~/.datamind-context/profiles/{profile}/wiki/index.md
```

## 背后自动做了什么

使用文件夹时，DataMind 会：

- 把资料抽取到托管目录，不修改原文件。
- 建 RAG 知识库。
- 建 GraphRAG 知识图谱。
- 生成轻量 Wiki：`index.md`、`sources/`、`user/preferences.md`、`log.md`。
- 把高价值问答沉淀到 `questions/` 和 `syntheses/`。
- 记录最近使用的 profile。
- 把高价值偏好写入全局 session `global`、Wiki preferences 和结构化记忆库。

托管目录在：

```text
~/.datamind-context/profiles/{profile}/data
```

动态记忆在：

```text
~/.datamind-context/interactions/global/events.jsonl
~/.datamind-context/memories/global/memory.md
~/.datamind-context/skills/global/
~/.datamind-context/memory.db
```

轻量 Wiki 在：

```text
~/.datamind-context/profiles/{profile}/wiki
```

查询时，DataMind 会先带上 Wiki、相关结构化记忆和全局 Markdown 记忆，再进入 RAG 或 GraphRAG。

## 支持哪些文件

- `.txt`
- `.md`
- `.pdf`
- `.csv`
- `.tsv`
- `.xlsx`
- `.xls`
- `.docx`
- `.pptx`

音频和视频默认不开启。需要时这样说：

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹，开启音视频转写。
```

## 常见问题

### 我还需要记 session 吗？

不需要。默认就是：

```text
global
```

### 我还需要记 profile 吗？

通常不需要。DataMind 会记住最近使用的 profile。

只有当你有多个资料库，想明确指定其中一个时，再说 profile 名字。

### 会不会改我的原始文件？

默认不会。DataMind 会把资料复制或抽取到托管目录，然后索引托管目录。

### 发布包里会带我的个人资料吗？

不会。发布包只包含插件代码和文档，不包含任何用户运行时数据。

从 0.8.0 开始，发布包可以包含一份干净的 DataMind 源码副本：

```text
vendor/datamind/
```

这只是运行 DataMind 所需的源码和模板配置，不包含用户数据、索引、向量库、Profile、Session 或 API key。

不会打包：

- `~/.datamind-context/`
- `memory.db`
- `profiles.json`
- `events.jsonl`
- `memory.md`
- 用户 profile、session、Wiki 或 generated skill
- `.datamind-repo-root` 本机路径标记
- `.env` API 配置文件
- `.venv` Python 虚拟环境
- `storage/` 向量库和图谱索引

## 工具列表

日常入口：

| 工具 | 说明 |
|---|---|
| `datamind_use_folder` | 使用或更新文件夹，生成托管 profile、索引和 Wiki；默认先做增量探测，无索引相关变化时跳过重建 |
| `datamind_ask` | 使用最近 profile、Wiki、结构化记忆和全局 session 自动问答 |
| `datamind_remember` | 记录偏好、决策和高价值交互，写入 Markdown/Wiki 和结构化记忆 |
| `datamind_save_memory` | 将交互封装为 Memory / Skill Markdown，并索引到结构化记忆 |
| `datamind_lint_wiki` | 检查 Wiki 健康度 |

高级入口：

| 工具 | 说明 |
|---|---|
| `datamind_ingest_folder` | 详细控制资料抽取和 Wiki 生成 |
| `datamind_refresh_folder` | 重建 RAG / GraphRAG 索引 |
| `datamind_rag_query` | 显式 RAG 查询 |
| `datamind_graph_query` | 显式 GraphRAG 查询 |
| `datamind_record_interaction` | 追加结构化交互日志 |
| `datamind_consolidate_memory` | 详细控制 Memory / Skill 生成和注入 |
| `datamind_search_memory` | 直接搜索结构化记忆库 |
| `datamind_record_feedback` | 记录某次 DataMind 回答后的确认、纠错或重试信号；负反馈会沉淀为 `feedback_hint` |
| `datamind_feedback_status` | 查看反馈轨迹、反馈事件和近期纠错状态 |
| `datamind_list_profiles` | 查看 profile |
| `datamind_list_memories` | 查看 session、Memory、Skill 和结构化记忆统计 |
| `datamind_status` | 查看索引和 Wiki 状态 |

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

`memory.db` 同时保存结构化 memory items、DataMind 问答反馈轨迹和下一轮反馈事件。

这些是用户本地运行数据，不应提交到 GitHub 发布包。

## 更多文档

```text
USAGE.md          # 同步保留的新手使用教程
INSTALL.md        # 安装、验证、隐私和发布说明
RELEASE_NOTES.md  # 版本更新说明
```
