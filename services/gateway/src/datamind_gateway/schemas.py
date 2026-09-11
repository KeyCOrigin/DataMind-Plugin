from __future__ import annotations

from typing import Any

from datamind_contracts import ExternalBatch


GATEWAY_TOOLS = [
    {"name": "datamind_agent_retrieve", "description": "Ask DataMind RetrieveAgent.", "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}, "_context": {"type": "object"}}, "required": ["message"]}},
    {"name": "datamind_agent_store", "description": "Ask DataMind StoreAgent.", "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}, "confirm": {"type": "boolean"}, "source_trust": {"type": "string", "enum": ["internal", "external"], "default": "internal"}, "_context": {"type": "object"}}, "required": ["message", "confirm"]}},
    {"name": "datamind_agent_status", "description": "Inspect Agent Runtime status.", "inputSchema": {"type": "object", "properties": {"_context": {"type": "object"}}}},
    {"name": "datamind_external_source_status", "description": "Inspect an external source handoff.", "inputSchema": {"type": "object", "properties": {"source_key": {"type": "string"}, "_context": {"type": "object"}}, "required": ["source_key"]}},
    {"name": "datamind_external_ingest_submit", "description": "Submit an asynchronous external ingest batch.", "inputSchema": {"type": "object", "properties": {"batch": {"type": "object"}, "_context": {"type": "object"}}, "required": ["batch"]}},
    {"name": "datamind_external_job_status", "description": "Get external ingest job status.", "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}, "_context": {"type": "object"}}, "required": ["job_id"]}},
    {"name": "datamind_external_receipt_get", "description": "Get receipts for an external ingest job.", "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}, "_context": {"type": "object"}}, "required": ["job_id"]}},
    {"name": "datamind_profile_list", "description": "List profiles allowed by the current identity.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "datamind_profile_status", "description": "Inspect one allowed profile.", "inputSchema": {"type": "object", "properties": {"profile_id": {"type": "string"}}}},
]
