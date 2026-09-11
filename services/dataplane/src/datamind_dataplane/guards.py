from __future__ import annotations

import re
from pathlib import Path

_DANGEROUS_SQL = re.compile(r"\b(drop|alter|attach|detach|pragma|vacuum|delete|update|insert|replace|create)\b", re.I)


def guard_args(name: str, args: dict, *, profile_root: Path) -> None:
    for key in ("path", "folder_path", "data_dir"):
        if key not in args:
            continue
        value = args[key]
        if not isinstance(value, str) or not value.strip():
            raise PermissionError("path must be a non-empty string")
        candidate = Path(value).expanduser().resolve()
        if candidate != profile_root and profile_root not in candidate.parents:
            raise PermissionError("path is outside the tenant profile data root")
    if name == "db_query_sql":
        sql = str(args.get("sql") or "")
        if not re.match(r"^\s*(select|with)\b", sql, re.I) or _DANGEROUS_SQL.search(sql) or ";" in sql.rstrip().rstrip(";"):
            raise PermissionError("db_query_sql only permits one read-only SELECT/WITH statement")
    writes = {"kb_add_text", "kb_add_file", "kb_add_path", "kb_reindex", "db_import_records", "db_import_csv",
              "graph_upsert_triples", "graph_add_triples_from_text", "memory_save", "memory_forget", "skill_upsert",
              "pdf_extract_text"}
    if name in writes and args.get("confirm") is not True:
        raise PermissionError("DataPlane write requires confirm=true")
