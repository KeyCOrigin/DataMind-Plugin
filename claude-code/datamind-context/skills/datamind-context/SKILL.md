---
name: datamind-context
description: Use DataMind from Claude Code to refresh a local folder into a RAG/GraphRAG knowledge base, then query document knowledge or graph relationships.
---

# DataMind Context

Use this skill when the user wants Claude Code to use DataMind, query a registered local folder, refresh a knowledge base, or ask about knowledge graph relationships in local documents.

## LLM Wiki Layer

DataMind maintains a lightweight Markdown Wiki for each profile under `~/.datamind-context/profiles/{profile}/wiki/`.

- `index.md` is the high-level map for the profile.
- `sources/` contains one provenance page per extracted source.
- `questions/` contains high-value questions captured from Claude Code conversations.
- `syntheses/` contains reusable answer-derived synthesis notes.
- `user/preferences.md` contains profile-specific durable preferences.
- `log.md` records Wiki refreshes.

Treat the Wiki as accumulated working knowledge. RAG and GraphRAG remain the source-grounded retrieval layer. When answering, prefer `datamind_ask`; it will automatically combine the Wiki, relevant structured memory, global session memory, and the relevant retrieval mode. High-value answers are captured into `questions/` and `syntheses/` in auto mode.

## Structured Memory Layer

DataMind also maintains a MemOS-inspired structured memory index at `~/.datamind-context/memory.db`.

- `datamind_remember` writes durable preferences, decisions, workflows, and high-value interactions to the legacy Markdown/Wiki path and to structured memory.
- `datamind_save_memory` and `datamind_consolidate_memory` keep writing `memory.md` and generated skill Markdown, and also index summaries and skills into structured memory.
- `datamind_ask`, `datamind_rag_query`, and `datamind_graph_query` add matching structured memory items to query context when available.
- `datamind_search_memory` directly searches structured memory without modifying it.
- Query tools also return a `feedback_trace.id`. Use `datamind_record_feedback` when the user confirms, corrects, or asks to redo a DataMind answer; negative feedback is saved as `feedback_hint` structured memory for future similar questions.
- Use `datamind_feedback_status` to inspect recent answer traces and feedback events.

Structured memory is additive. If `memory.db`, SQLite FTS, or memory search is unavailable, the plugin should continue using the legacy Wiki + Markdown memory path.

## Default Behavior

- Do not ask the user to provide a session name. Leave `session_id` unset unless the user explicitly names one. DataMind will use the global session `global`.
- Do not force the user to provide a profile name. When the user gives a folder but no profile, call `datamind_use_folder` with only `folder_path`; DataMind will create a profile automatically and return its name.
- For normal updates, call `datamind_use_folder` without `clean` or `force_rebuild`. The simple entrypoint does manifest-based change detection, ignores Office `~$` lock files, and skips RAG/GraphRAG rebuilds when no index-relevant files changed.
- When the user asks a follow-up question and does not name a profile, call `datamind_ask` without `profile`; DataMind will use the last DataMind profile by default.
- Tell the user the auto-created profile name after `datamind_use_folder` returns, but keep future prompts simple.

## Automatic Memory Capture

Automatically call `datamind_remember` without asking for a session when the user expresses a durable, high-value pattern, including:

- A preference about answer format, language, ordering, evidence, verbosity, or workflow.
- A repeated correction or stable instruction, such as "以后都这样处理".
- A project convention, naming rule, directory rule, data handling rule, or safety constraint.
- A decision that should influence future DataMind operations.

Do not auto-record secrets, API keys, passwords, tokens, temporary one-off facts, or noisy step-by-step logs. Keep each auto memory short and actionable. Include metadata like `{"kind":"auto_high_value_habit"}` when useful.

## Workflow

Prefer the simple tools first:

1. Use `datamind_use_folder` when the user wants to start using or update a folder. It copies/extracts supported files into a managed profile, refreshes indexes when needed, and generates the profile Wiki.
2. Use `datamind_ask` when the user asks a question. Pass `profile` only when the user names one; leave `session_id` unset by default; leave `mode=auto` unless the user explicitly asks for graph/RAG.
3. Use `datamind_remember` when the user wants Claude Code to remember a preference, decision, repeated workflow, or important interaction, and also for high-value habits detected automatically. This also writes Wiki preferences.
4. Use `datamind_save_memory` when the user asks to summarize, persist, package, or inject memory/skills.
5. Use `datamind_lint_wiki` when the user asks to check Wiki quality, health, consistency, broken links, or whether the Wiki is getting messy.

Use advanced tools only when needed:

- `datamind_ingest_folder` for detailed ingestion options.
- `datamind_refresh_folder` for raw DataMind-compatible folders.
- `datamind_rag_query` for explicit RAG-only questions.
- `datamind_graph_query` for explicit GraphRAG-only questions.
- `datamind_record_interaction` for structured message logs.
- `datamind_consolidate_memory` for detailed memory packaging options.
- `datamind_search_memory` for direct structured-memory lookup.
- `datamind_record_feedback` when a DataMind answer receives next-turn correction, confirmation, or redo feedback.
- `datamind_feedback_status` for feedback trace inspection.
- `datamind_lint_wiki` for Wiki health reports.
- `datamind_status`, `datamind_list_profiles`, and `datamind_list_memories` for inspection.

## Notes

- DataMind uses the repository `.env` for LLM and embedding credentials.
- `profile` is the stable handle Claude Code can reuse after a folder is refreshed.
- The default dynamic memory session is `global`.
- Managed profile data is stored under `~/.datamind-context/profiles/{profile}/data`.
- The profile Wiki is stored under `~/.datamind-context/profiles/{profile}/wiki`.
- Structured memory is stored under `~/.datamind-context/memory.db`.
- Dynamic interaction logs, memories, and generated skill files are stored under `~/.datamind-context/`.
- Audio/video transcription is best-effort and only runs when `transcribe_media` is true.
