# DataMind Context Plugin (Claude Code) 安装与发布说明

本目录是 DataMind Context **Claude Code Plugin** 的发布包内容。它包含插件代码、技能说明、图标、使用文档，以及可选的 DataMind runtime 源码。它不包含任何用户运行时数据。

## 包内包含

```text
datamind-context/
  .claude-plugin/
    plugin.json                    # Claude Code 插件清单
    mcp.json                       # 用 ${CLAUDE_PLUGIN_ROOT} 引用 MCP 启动脚本
    marketplace.json               # 让 `claude plugin install` 能发现本插件
  hooks/hooks.json                 # SessionStart 钩子，按需懒装依赖
  scripts/bootstrap_claude.sh      # SessionStart 实际执行的脚本
  README.md
  USAGE.md
  INSTALL.md
  RELEASE_NOTES.md
  install.sh
  assets/
  skills/                          # SKILL.md，自动触发指引
  src/                             # MCP server 源码
  vendor/datamind/                 # DataMind runtime（可选内置）
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
2. 已安装 Claude Code（`claude` CLI 在 PATH 中）：https://docs.claude.com/claude-code
3. 有可用的 LLM 和 embedding API 配置。

从 0.8.0 开始，发布包内置 `vendor/datamind/`，用户不需要先单独 clone DataMind 主仓库。

## 安装方式 A: 一键安装（推荐）

进入解压后的目录运行:

```bash
cd /path/to/extracted/datamind-context
./install.sh
```

如果之前已经安装过，希望覆盖:

```bash
./install.sh --force
```

`install.sh` 会:

- 在 `vendor/datamind/.venv` 中创建 venv 并安装 `requirements.txt`。
- 如果 `.env` 不存在，从 `.env.example` 复制一份。
- 调用 `claude plugin marketplace add` 把当前目录注册为本地 marketplace。
- 调用 `claude plugin install datamind-context@datamind` 完成安装。

然后:

1. 编辑 `vendor/datamind/.env`，填入 LLM 和 embedding 凭据。
2. 重启 Claude Code（已开启的会话可运行 `/reload-plugins`）。
3. 验证：`claude mcp list` 应显示 `plugin:datamind-context:datamind-context ✓ Connected`。

## 安装方式 B: 跳过依赖安装

如果你已经在另一个位置（例如 Codex 的安装目录 `~/.codex/marketplaces/datamind/plugins/datamind-context/vendor/datamind/.venv`）配好了 venv，可以跳过本目录建 venv：

```bash
./install.sh --skip-deps
```

`src/run_datamind_mcp.sh` 会按以下顺序探测可用 Python：

1. `${DATAMIND_PYTHON}` 环境变量
2. `${CLAUDE_PLUGIN_DATA}/.venv/bin/python`（Claude Code 持久数据目录，由 SessionStart 钩子建立）
3. `~/.codex/marketplaces/*/plugins/datamind-context/vendor/datamind/.venv/bin/python`（Codex 安装位置）
4. 当前插件 `vendor/datamind/.venv/bin/python`
5. 系统 `python3`

也就是说，**如果你已经在 Codex 装过 DataMind，Claude Code 会自动复用那份 venv**。

## 安装方式 C: 使用已有 DataMind 仓库

如果你已 clone DataMind 主仓库并希望以它作为 runtime:

```bash
./install.sh --repo-root /path/to/DataMind
```

## Windows 安装方式

Windows 用户不需要 Git Bash 或 WSL，使用配套的 `install.ps1`：

```powershell
cd claude-code\datamind-context
.\install.ps1
```

如果 PowerShell 默认 ExecutionPolicy 阻止脚本运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

支持的参数：

| 参数 | 等价的 Bash 选项 | 作用 |
|---|---|---|
| `-Force` | `--force` | 卸载已有插件并重新安装 |
| `-SkipDeps` | `--skip-deps` | 跳过 venv 与依赖安装；交给 SessionStart 钩子懒加载 |
| `-RepoRoot <path>` | `--repo-root <path>` | 指定外部 DataMind 仓库 |
| `-PythonExe <path>` | `--python <path>` | 指定 Python 解释器 |

`install.ps1` 会做几件 Windows 专属的事：

1. 在 `vendor\datamind\.venv\Scripts\python.exe` 建 venv。
2. **把 `.claude-plugin\mcp.windows.json` 覆盖成 `.claude-plugin\mcp.json`**，让 Claude Code 在 Windows 上调用 `powershell.exe -File ${CLAUDE_PLUGIN_ROOT}\src\run_datamind_mcp.ps1`，而不是 Bash 脚本。
3. 调用 `claude plugin marketplace add` 和 `claude plugin install` 完成注册（与 Linux/macOS 流程相同）。

注意：`claude` CLI 必须在 PATH 中。如果 PowerShell 找不到 `claude`，确认你已经按 https://docs.claude.com/claude-code 的指引装好 Claude Code，并把它加进 PATH。

## 验证安装

在 Claude Code 里输入:

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

## 主要特性

- 一键安装: release 包内置 DataMind runtime，不需要用户先 clone 主仓库。
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

这些是用户本地运行数据，不应提交到 GitHub 发布包。

## 故障排查

如果 Claude Code 能看到插件但调用失败，优先检查:

1. `claude mcp list` 是否显示 `plugin:datamind-context:datamind-context ✓ Connected`。
2. `claude plugin validate /path/to/datamind-context` 是否通过。
3. DataMind 依赖是否已安装；必要时重新运行 `./install.sh --force`。
4. DataMind runtime 的 `.env` 是否配置了 LLM 和 embedding。
5. 重启 Claude Code 后是否生效（或运行 `/reload-plugins`）。
6. 用 `claude --debug` 启动，看 MCP 初始化日志。

也可以临时使用环境变量覆盖:

```bash
export DATAMIND_REPO_ROOT=/path/to/DataMind
export DATAMIND_PYTHON=/path/to/specific/python
```

## 与 Codex / Cursor 版本的关系

三家版本共享同一份 `vendor/datamind/` 运行时和同一套 MCP server (`src/datamind_mcp.py`)，用户运行时数据目录都是 `~/.datamind-context/`，所以三个 IDE 之间可以无缝共享 profile、Wiki 和结构化记忆。

主要差异只在打包层:

| 维度 | Codex 版本 | Claude Code 版本 | Cursor 版本 |
|---|---|---|---|
| 清单 | `.codex-plugin/plugin.json` | `.claude-plugin/plugin.json` | `.cursor-plugin/plugin.json` |
| MCP 配置 | `.mcp.json`（相对路径） | `.claude-plugin/mcp.json`（`${CLAUDE_PLUGIN_ROOT}`） | `mcp.json`（`${userHome}`） |
| 安装目录 | `~/.codex/marketplaces/datamind/plugins/datamind-context/` | Claude Code plugin cache（自动） | `~/.cursor/plugins/local/datamind-context/` |
| Marketplace | `~/.codex/config.toml` | `claude plugin marketplace add` | Cursor 自动发现 |
| 自动触发 | Skills (`SKILL.md`) | Skills (`SKILL.md`) | Skills + Cursor Rules (`~/.cursor/rules/`) |
| 启用位置 | Codex 插件列表 | 装完即生效 | `Settings -> Plugins -> Local Plugins` |

## 卸载

```bash
claude plugin uninstall datamind-context@datamind
claude plugin marketplace remove datamind
```

如需保留持久 venv 数据（`${CLAUDE_PLUGIN_DATA}`）请加 `--keep-data`。

## 发布建议

发布到 GitHub Release 时，建议上传压缩包并在 release note 中说明:

- 版本号。
- 是否内置 `vendor/datamind/` runtime。
- 支持的 DataMind commit 或版本，如果没有内置 runtime。
- 是否包含结构化记忆能力。
- 发布包不包含任何用户 profiles、sessions 或 memory 数据。
