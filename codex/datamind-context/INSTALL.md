# DataMind Context Plugin 安装与发布说明

本目录是 DataMind Context Codex Plugin 的发布包内容。它包含插件代码、技能说明、图标、使用文档，以及可选的 DataMind runtime 源码。它不包含任何用户运行时数据。

## 包内包含

```text
datamind-context/
  .codex-plugin/plugin.json
  .mcp.json
  README.md
  USAGE.md
  INSTALL.md
  RELEASE_NOTES.md
  install.sh
  assets/
  skills/
  src/
  vendor/datamind/        # release 包可选内置的 DataMind runtime 源码
```

## 包内不包含

以下内容不会进入发布包:

- `~/.datamind-context/` 下的用户 profiles、Wiki、session、memory、skills。
- `memory.db` 结构化记忆数据库。
- `events.jsonl`、`memory.md`、`skill.md` 等用户动态记忆产物。
- `.datamind-repo-root` 本机路径标记。
- `.env` API 配置文件。
- `.venv` Python 虚拟环境。
- `storage/` 向量库和图谱索引。
- `.DS_Store`、`__pycache__`、`.pytest_cache` 等本机缓存。

## 前置条件

1. 已安装 Python 3。
2. 已安装 Codex，并能启用本地插件。
3. 有可用的 LLM 和 embedding API 配置。

从 0.8.0 开始，如果使用带 `vendor/datamind/` 的 release 包，用户不需要先单独 clone DataMind 主仓库。安装脚本会使用包内 DataMind runtime，自动创建 `.venv` 并安装依赖。

如果你希望使用自己 clone 的 DataMind 仓库，也仍然可以通过 `--repo-root /path/to/DataMind` 指定。

## 安装方式 A: 从发布包一键安装

解压发布包后运行:

```bash
unzip datamind-context-plugin-codex-1.0.0.zip
cd datamind-context
./install.sh
```

如果之前已经安装过同名插件，并希望覆盖:

```bash
./install.sh --force
```

这会使用发布包内置的:

```text
vendor/datamind/
```

作为 DataMind runtime。

安装脚本会:

- 将插件复制到 `~/.codex/marketplaces/datamind/plugins/datamind-context/`。
- 将整个 `~/.codex/marketplaces/datamind/` 目录写成一个 Codex 兼容的 marketplace（包括 `.agents/plugins/marketplace.json`）。
- 在 `~/.codex/config.toml` 里追加（幂等）：
  ```toml
  [marketplaces.datamind]
  source_type = "local"
  source = "/Users/<you>/.codex/marketplaces/datamind"

  [plugins."datamind-context@datamind"]
  enabled = true
  ```
- 创建 DataMind runtime 的 `.venv` 并安装 `requirements.txt`。
- 如果没有 `.env`，从 `.env.example` 创建一份。

可以用 `DATAMIND_CODEX_MARKETPLACE` 环境变量覆盖 marketplace 名字（默认 `datamind`），如果你想把多个本地插件放到同一个 marketplace 里。

然后编辑安装目录里的 `.env`，填入 LLM 和 embedding 配置。安装脚本输出里会显示具体路径。

**注意**：Codex 是 **lazy** 的——它启动时不会立即 spawn datamind 进程，而是在你**第一次调用** `datamind_*` 工具（例如说"用 DataMind 看一下 profile"）时才把它拉起来。这是 Codex 的设计，跟 Claude Code 启动即起的行为不同。

## 安装方式 B: 使用已有 DataMind 仓库

如果你已经 clone 了 DataMind 主仓库，可以运行:

```bash
cd /path/to/extracted/datamind-context
./install.sh --repo-root /path/to/DataMind
```

如果你想先跳过依赖安装:

```bash
./install.sh --repo-root /path/to/DataMind --skip-deps
```

也可以指定 Python:

```bash
./install.sh --python /usr/bin/python3
```

## 安装方式 C: 从 DataMind 仓库内安装

如果插件位于 DataMind 仓库内的 `plugins/datamind-context/`，直接运行:

```bash
cd /path/to/DataMind
./scripts/install_codex_plugin.sh
```

然后重启 Codex，在插件入口启用 `DataMind Context`。

## Windows 安装方式

Windows 用户不需要 Git Bash 或 WSL，使用配套的 `install.ps1`：

```powershell
cd codex\datamind-context
.\install.ps1
```

如果 PowerShell 默认 ExecutionPolicy 阻止脚本运行，可以用：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

支持的参数（PowerShell 风格）：

| 参数 | 等价的 Bash 选项 | 作用 |
|---|---|---|
| `-Force` | `--force` | 覆盖已有安装 |
| `-SkipDeps` | `--skip-deps` | 跳过 venv 和依赖安装 |
| `-RepoRoot <path>` | `--repo-root <path>` | 指定外部 DataMind 仓库 |
| `-PythonExe <path>` | `--python <path>` | 指定 Python 解释器 |

`install.ps1` 在装的最后会**把 `.mcp.windows.json` 复制覆盖 `.mcp.json`**，让 Codex 在 Windows 上启动 MCP server 时调用 `powershell.exe -File src\run_datamind_mcp.ps1`，而不是去执行 Bash 脚本。这一步是 Windows 专属，不影响 Linux/macOS 流程。

## 验证安装

在 Codex 里输入:

```text
用 DataMind 看一下现在有哪些 profile。
```

第一次没有 profile 是正常的。接着可以使用一个资料文件夹:

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹。
```

然后直接提问:

```text
用 DataMind 问：这批资料里最重要的结论是什么？
```

## 常用说法

```text
用 DataMind 使用这个文件夹：/你的/资料/文件夹。
```

```text
用 DataMind 问：请总结这批资料的关键结论和下一步行动。
```

```text
用 DataMind 更新 workdocs。
```

```text
用 DataMind 检查这个资料库的 Wiki。
```

```text
用 DataMind 搜索记忆：资料总结的输出格式偏好。
```

## 主要特性

- 一键安装: release 包可内置 DataMind runtime，不需要用户先 clone 主仓库。
- 本地资料库 RAG: 支持把文件夹抽取成托管知识库并进行语义问答。
- GraphRAG: 支持实体关系和多跳关系查询。
- 低打扰 profile: 不指定 profile 时自动创建或使用最近 profile。
- 低打扰 session: 默认使用全局 session `global`。
- Markdown Wiki: 为每个 profile 生成可读、可沉淀、可检查的 Wiki。
- 高价值问答沉淀: 方案、比较、风险、决策类回答可自动写入 `questions/` 和 `syntheses/`。
- MemOS-inspired 结构化记忆: 在不破坏 Markdown 行为的前提下，将偏好、决策、workflow、summary 和 skill 索引到 `~/.datamind-context/memory.db`。
- 兼容降级: 结构化记忆不可用时，自动退回 Wiki + Markdown memory 路径。
- Wiki Lint: 检查必要页面、坏链接、孤立来源页和缺失 synthesis。
- 原始文件安全: 默认不修改用户原始资料文件夹，先抽取到托管目录再建索引。

## 运行时数据位置

插件运行时会在用户机器上创建:

```text
~/.datamind-context/
  profiles.json
  profiles/{profile}/data/
  profiles/{profile}/wiki/
  memory.db
  interactions/{session}/events.jsonl
  memories/{session}/memory.md
  skills/{session}/*.md
  runtime/query-contexts/
```

这些都是用户本地运行数据，不应提交到 GitHub 发布包。

## 故障排查

如果 Codex 能看到插件但调用失败，优先检查:

1. 插件安装目录下的 `.datamind-repo-root` 是否指向有效 DataMind runtime。
2. 如果是内置 runtime，检查 `~/.codex/marketplaces/datamind/plugins/datamind-context/vendor/datamind/` 是否存在。
3. DataMind 依赖是否已安装；必要时重新运行 `./install.sh --force`。
4. DataMind runtime 的 `.env` 是否配置了 LLM 和 embedding。
5. 重启 Codex 后是否重新启用了插件。

也可以临时使用环境变量覆盖仓库位置:

```bash
export DATAMIND_REPO_ROOT=/path/to/DataMind
```

## 发布建议

发布到 GitHub Release 时，建议上传压缩包并在 release note 中说明:

- 版本号。
- 是否内置 `vendor/datamind/` runtime。
- 支持的 DataMind commit 或版本，如果没有内置 runtime。
- 是否包含结构化记忆能力。
- 发布包不包含任何用户 profiles、sessions 或 memory 数据。
