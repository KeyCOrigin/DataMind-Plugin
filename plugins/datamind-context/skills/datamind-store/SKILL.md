---
name: datamind-store
description: Use the authenticated DataMind StoreAgent through Gateway.
---

少量数据使用 `datamind_agent_store`，并显式传入 `confirm: true`；多个独立数据项
必须使用 `datamind_agent_store_batch`，一次请求传入 `items`，不要在客户端循环
调用单条工具。该接口只创建一个 StoreAgent 会话，但每个 item 仍独立选择目标并
返回独立真实回执。
外部邮箱、飞书或数据库数据需要批量处理时，先在外部 MCP 中使用批量读取工具，
一次连接读取多个记录，再使用 `datamind_external_ingest_submit` 提交分块；不要
逐条重新建立外部连接。该批量入口仍调用同一个 StoreAgent，只负责幂等、进度、
回执和 checkpoint。

不要调用 DataPlane 的底层工具；Gateway 和 DataPlane 会执行回执和权限隔离。

文件入库时，StoreAgent 应优先使用 DataPlane 内部的
`kb_ingest_document`；目录入库使用 `kb_ingest_path`。这两个工具负责在
DataPlane 内完成 TXT、Markdown、CSV、TSV、DOCX、XLSX 和 PDF 的统一抽取，
并返回抽取方式、字符数和截断状态。扫描版 PDF 只有在明确需要时才传
`ocr: true`，如果运行环境没有 OCR 依赖必须报告失败，不得把空正文当成成功。

多个文件使用 `kb_ingest_path`，不要让 Codex 自己逐文件读取、拼接或重复
启动入库流程。表格应保留完整行，不得默认只取前几行；如果超过
`max_chars`，必须在回执中标记 `truncated`。

成功整理来源后，可由 StoreAgent 调用内部 `wiki_upsert_source` 写入来源页面；
用户明确纠正回答时，可调用 `memory_record_feedback`，但不得把外部正文或
凭据写入反馈和记忆。普通对话不应无条件写 Wiki。

Embedding 配置边界：Embedding 只由 DataPlane 使用独立的
`DATAMIND__EMBEDDING__*` 配置生成。不要把 LLM 的地址、zcloud、Anthropic
地址或 LLM 密钥当作 Embedding 配置。DataPlane 报 Embedding 超时、不可用或
维度错误时，必须报告入库失败，不能声称成功，也不能绕过向量索引伪造成功。
