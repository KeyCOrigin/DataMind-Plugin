---
name: datamind-store
description: Use the authenticated DataMind StoreAgent through Gateway.
---

少量数据使用 `datamind_agent_store`，并显式传入 `confirm: true`。
外部邮箱、飞书或数据库数据需要批量处理时，先在外部 MCP 中使用批量读取工具，
一次连接读取多个记录，再使用 `datamind_external_ingest_submit` 提交分块；不要
逐条重新建立外部连接。该批量入口仍调用同一个 StoreAgent，只负责幂等、进度、
回执和 checkpoint。

不要调用 DataPlane 的底层工具；Gateway 和 DataPlane 会执行回执和权限隔离。
