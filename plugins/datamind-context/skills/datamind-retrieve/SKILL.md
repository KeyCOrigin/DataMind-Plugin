---
name: datamind-retrieve
description: Use the authenticated DataMind RetrieveAgent through Gateway.
---

Call `datamind_agent_retrieve` with the user question. Do not expect or request
`kb_*`, `db_*`, `graph_*`, `memory_*`, or `skill_*` tools; those are private to
DataMind's internal RetrieveAgent/DataPlane session.

RetrieveAgent 可以在需要时读取 DataPlane 内部的 `wiki_search`、`wiki_status` 和
`memory_recall`。回答资料问题仍以 KB/Graph 检索结果为事实依据，Wiki 和 Memory
只作为补充上下文；不要把 Wiki 中的用户纠错当成未经验证的事实。

RetrieveAgent 还可以使用 DataPlane 的只读实用工具 `utility_calculate` 和
`utility_current_time`。需要精确数学计算时调用前者，不要自行心算；涉及当前日期
或时间时调用后者。计算器只接受受限数学表达式，不执行任意 Python；这两个工具
不会写入 KB、DB、Graph、Memory 或 Skills，StoreAgent 和外部入库任务不能使用它们。
