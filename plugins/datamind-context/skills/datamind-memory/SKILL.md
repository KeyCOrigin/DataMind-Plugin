---
name: datamind-memory
description: Use DataMind's tenant-scoped memory, feedback and Wiki experience layer.
---

通过 `datamind_agent_retrieve` 处理查询；不要让 Codex 直接调用 DataPlane 的
`memory_*` 或 `wiki_*` 工具。DataMind 内部 RetrieveAgent 可以读取相关 Memory
和 Wiki，事实结论仍必须以 KB/Graph 检索结果为依据。

当用户明确要求记住偏好、决定或可复用流程时，由 StoreAgent 保存到当前
profile 的 Memory。不要保存 API key、密码、Token、Cookie 或完整外部邮件正文。

用户明确纠正或确认回答时，StoreAgent 可以记录 `memory_record_feedback`；反馈
必须包含原问题和纠正内容，负面反馈不能直接覆盖原知识。

来源文档成功入库后，可以由 StoreAgent 使用 `wiki_upsert_source` 写入来源页。
普通查询不要无条件写 Wiki；只有用户要求整理、总结或沉淀时才写入。
