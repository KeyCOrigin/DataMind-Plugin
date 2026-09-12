from __future__ import annotations

from datamind_contracts import AuthorizationError

READ_TOOLS = {"kb_search", "kb_list_documents", "kb_count", "db_list_tables", "db_describe_table", "db_query_sql", "db_query_nl",
              "graph_search_entities", "graph_traverse", "graph_neighbors", "skill_search", "skill_get", "skill_list",
              "memory_recall", "memory_list_profiles", "wiki_search", "wiki_status"}
UTILITY_TOOLS = {"utility_calculate", "utility_current_time"}
WRITE_TOOLS = {"kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex", "db_import_records", "db_import_csv",
               "kb_ingest_document", "kb_ingest_path", "graph_upsert_triples", "graph_add_triples_from_text",
               "memory_save", "memory_forget", "memory_record_interaction", "memory_record_feedback",
               "skill_upsert", "wiki_upsert_source"}
EXTERNAL_WRITE_TOOLS = {
    "kb_add_text",
    "kb_add_file",
    "kb_ingest_document",
    "kb_ingest_path",
    "db_import_records",
    "db_import_csv",
    "graph_upsert_triples",
}


def authorize(tool: str, scopes: set[str]) -> None:
    if "datamind.dataplane.admin" in scopes and tool in READ_TOOLS | WRITE_TOOLS | UTILITY_TOOLS:
        return
    if tool in UTILITY_TOOLS and "datamind.dataplane.read" not in scopes:
        raise AuthorizationError("read scope is required for this utility")
    if tool in READ_TOOLS and "datamind.dataplane.read" not in scopes:
        raise AuthorizationError("read scope is required")
    if tool in WRITE_TOOLS:
        if "datamind.dataplane.write" in scopes:
            return
        if "datamind.dataplane.external_write" in scopes and tool in EXTERNAL_WRITE_TOOLS:
            return
        raise AuthorizationError("write scope is required for this tool")
    if tool not in READ_TOOLS | WRITE_TOOLS | UTILITY_TOOLS:
        raise AuthorizationError(f"tool is not exposed by DataPlane: {tool}")
