# DataMind-Plugin

Three packaging variants of the **DataMind** AI agent plugin — one for **Codex**, one for **Claude Code**, one for **Cursor**. They all expose the same 17 MCP tools (RAG, GraphRAG, Wiki, structured memory, feedback loop) over the same DataMind runtime, and they share the same on-disk data location so switching IDEs preserves your profiles and memories.

## What does DataMind do?

It turns "chatting with an AI" into an accumulating local knowledge asset. Concretely:

- **`datamind_use_folder`** — point it at any folder of PDF/docx/xlsx/markdown/etc. and it builds a managed RAG + GraphRAG index, never touching your originals.
- **`datamind_ask`** — answer a question; the model gets Wiki snippets, structured memory, and retrieved chunks all merged in.
- **`datamind_remember`** — capture a durable preference, decision, or workflow.
- **Wiki layer** at `~/.datamind-context/profiles/{profile}/wiki/` — human-readable Markdown that accumulates as you ask high-value questions.
- **Structured memory** at `~/.datamind-context/memory.db` — MemOS-style index of preferences/decisions/workflows.
- **Feedback loop** — every answer returns a `feedback_trace.id`; corrections become `feedback_hint` memory for similar future questions.

Full tool list is in any of the three sub-directories' `USAGE.md`.

## Pick your IDE

```text
DataMind-Plugin/
├── codex/datamind-context/         ← Codex users
├── claude-code/datamind-context/   ← Claude Code users
└── cursor/datamind-context/        ← Cursor users
```

### Install in 3 lines

```bash
git clone https://github.com/OpenDCAI/DataMind-Plugin.git
cd DataMind-Plugin

# Pick the directory matching your IDE:
cd codex/datamind-context        && ./install.sh   # Codex
# cd claude-code/datamind-context && ./install.sh   # Claude Code
# cd cursor/datamind-context      && ./install.sh   # Cursor
```

Each `install.sh` is self-contained: it creates a Python venv under `vendor/datamind/.venv`, installs `requirements.txt`, registers the plugin with the corresponding IDE, and tells you where to put your LLM/embedding API keys.

After install, edit `vendor/datamind/.env` (each variant has its own copy under its install location) and restart your IDE.

### Windows users

Windows isn't a second-class citizen. Each variant ships a PowerShell counterpart of every Bash script:

```powershell
git clone https://github.com/OpenDCAI/DataMind-Plugin.git
cd DataMind-Plugin

# Pick one:
cd codex\datamind-context        ; .\install.ps1   # Codex
# cd claude-code\datamind-context ; .\install.ps1   # Claude Code
# cd cursor\datamind-context      ; .\install.ps1   # Cursor
```

`install.ps1` does three things `install.sh` doesn't on Unix:

1. Creates the venv under `vendor\datamind\.venv\Scripts\python.exe` (Windows venv layout).
2. Replaces the bundled `mcp.json` with `mcp.windows.json`, so the IDE spawns `powershell.exe -File run_datamind_mcp.ps1` instead of trying to execute the Bash launcher.
3. Honors `-Force`, `-SkipDeps`, `-RepoRoot`, `-PythonExe` flags (PowerShell-style equivalents of the Bash `--force`, `--skip-deps`, etc.).

If your PowerShell execution policy blocks the script, run it once with:
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

## Per-IDE differences

|  | Codex | Claude Code | Cursor |
|---|---|---|---|
| Manifest | `.codex-plugin/plugin.json` | `.claude-plugin/plugin.json` | `.cursor-plugin/plugin.json` |
| MCP config | `.mcp.json` (relative path) | `.claude-plugin/mcp.json` (uses `${CLAUDE_PLUGIN_ROOT}`) | `mcp.json` (uses `${userHome}`) |
| Install location | `~/.codex/marketplaces/datamind/plugins/datamind-context/` | Claude Code plugin cache (auto-managed) | `~/.cursor/plugins/local/datamind-context/` |
| Auto-trigger | Skills (`SKILL.md`) | Skills (`SKILL.md`) | Skills + a global Cursor Rule installed to `~/.cursor/rules/datamind.mdc` |
| Marketplace | `~/.codex/config.toml` (auto-written) | `claude plugin marketplace add` | Auto-discovered from `~/.cursor/plugins/local/` |
| Verify | Codex plugin list | `claude mcp list` should show ✓ Connected | Cursor `Settings → Plugins → Local Plugins` |

## Cross-IDE data sharing

All three variants read and write the same paths under `~/.datamind-context/`. So if you build a profile in Codex and then switch to Claude Code, the same profile, Wiki, and memory are all there — no migration step needed.

```text
~/.datamind-context/
├── profiles.json                  # Profile registry
├── profiles/{profile}/data/       # Managed copies of source files
├── profiles/{profile}/wiki/       # Per-profile Markdown Wiki
├── memory.db                      # Structured memory (SQLite + FTS)
├── interactions/{session}/        # Dynamic event logs
├── memories/{session}/            # Consolidated memories
└── skills/{session}/              # Generated skill markdown
```

## Maintenance: the three copies

Each sub-directory is a **complete, independent** copy of the plugin — including `src/*.py` and `vendor/datamind/`. This lets you `git clone` and use any one of the three without depending on a build step or symlinks.

The trade-off: when you change the core MCP server or vendored DataMind code, you have to keep the three copies in sync. Use `scripts/sync-core.sh` (treats `codex/datamind-context/` as the source of truth) to copy `src/*.py` and `vendor/datamind/` to the other two.

```bash
./scripts/sync-core.sh             # Sync core code from codex/ to claude-code/ and cursor/
./scripts/sync-core.sh --check     # Dry-run; report differences without writing
```

Files that are **not** synced (each variant has its own):

- `install.sh`
- The IDE-specific manifest (`.{codex,claude,cursor}-plugin/`)
- The IDE-specific MCP config (`.mcp.json`, `.claude-plugin/mcp.json`, or `mcp.json`)
- `README.md`, `INSTALL.md`, `USAGE.md`, `RELEASE_NOTES.md`
- Cursor: `.cursor/rules/datamind.mdc`
- Claude Code: `hooks/`, `scripts/bootstrap_claude.sh`, `.claude-plugin/marketplace.json`
- The string "Codex" / "Claude Code" / "Cursor" inside `skills/datamind-context/SKILL.md`

When you tag a release, you can either:

1. **Single repo + GitHub Release zips**: zip each sub-directory separately as `datamind-context-plugin-codex-X.Y.Z.zip` etc.
2. **Single repo, users `git clone` directly**: tell users to `cd <variant>/datamind-context && ./install.sh`.

Both flows work.

## Repo structure

```text
DataMind-Plugin/
├── README.md                       # This file
├── .gitignore
├── scripts/
│   └── sync-core.sh                # Maintenance: keep three copies in sync
├── codex/
│   └── datamind-context/           # Self-contained Codex variant
├── claude-code/
│   └── datamind-context/           # Self-contained Claude Code variant
└── cursor/
    └── datamind-context/           # Self-contained Cursor variant
```

## License

MIT, same as upstream DataMind.

## Links

- DataMind upstream: https://github.com/zwt233/DataMind
