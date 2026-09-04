from __future__ import annotations

from datamind_contracts import AuthorizationError

READ_TOOLS = {"kb_search", "kb_list_documents", "kb_count", "db_list_tables", "db_describe_table", "db_query_sql", "db_query_nl",
              "graph_search_entities", "graph_traverse", "graph_neighbors", "skill_search", "skill_get", "skill_list",
              "memory_recall", "memory_list_profiles"}
WRITE_TOOLS = {"kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex", "db_import_records", "db_import_csv",
               "graph_upsert_triples", "graph_add_triples_from_text", "memory_save", "memory_forget", "skill_upsert"}
EXTERNAL_WRITE_TOOLS = {"kb_add_text", "kb_add_file", "db_import_records", "db_import_csv", "graph_upsert_triples"}


def authorize(tool: str, scopes: set[str]) -> None:
    if "datamind.dataplane.admin" in scopes and tool in READ_TOOLS | WRITE_TOOLS:
        return
    if tool in READ_TOOLS and "datamind.dataplane.read" not in scopes:
        raise AuthorizationError("read scope is required")
    if tool in EXTERNAL_WRITE_TOOLS and "datamind.dataplane.external_write" in scopes:
        return
    if tool in WRITE_TOOLS and "datamind.dataplane.external_write" in scopes:
        raise AuthorizationError("external_write cannot call this tool")
    if tool in WRITE_TOOLS and "datamind.dataplane.write" not in scopes:
        raise AuthorizationError("write scope is required")
    if tool in {"memory_save", "memory_forget", "skill_upsert", "kb_reindex", "graph_add_triples_from_text"} and "datamind.dataplane.external_write" in scopes:
        raise AuthorizationError("external_write cannot call this tool")
    if tool not in READ_TOOLS | WRITE_TOOLS:
        raise AuthorizationError(f"tool is not exposed by DataPlane: {tool}")
