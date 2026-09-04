---
name: datamind-store
description: Use the authenticated DataMind StoreAgent through Gateway.
---

Use `datamind_agent_store` for deliberate writes and explicit `confirm: true`.
Use `datamind_external_ingest_submit` for validated batches read from an
independent external MCP. Never attempt to call DataPlane capability tools;
Gateway and DataPlane enforce the receipt and scope boundaries.
