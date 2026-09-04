---
name: datamind-retrieve
description: Use the authenticated DataMind RetrieveAgent through Gateway.
---

Call `datamind_agent_retrieve` with the user question. Do not expect or request
`kb_*`, `db_*`, `graph_*`, `memory_*`, or `skill_*` tools; those are private to
DataMind's internal RetrieveAgent/DataPlane session.
