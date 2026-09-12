from datetime import datetime, timezone

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/src"))
sys.path.insert(0, str(ROOT / "services/dataplane/src"))
sys.path.insert(0, str(ROOT / "services/gateway/src"))

from datamind_contracts import AuthorizationError, ExternalBatch, ExternalItem, ExternalSource, RequestContext
from datamind_dataplane.authorization import authorize
from datamind_gateway.schemas import GATEWAY_TOOLS


def test_external_batch_is_typed_and_gateway_surface_is_narrow():
    batch = ExternalBatch(source=ExternalSource(provider="feishu", connection_id="c", resource_type="bitable", stream="app/table"),
                          items=[ExternalItem(external_id="r1", updated_at=datetime.now(timezone.utc), text="hello")], confirm=True)
    assert batch.schema_version == "1.0"
    names = {tool["name"] for tool in GATEWAY_TOOLS}
    assert "datamind_agent_retrieve" in names
    assert not any(name.startswith("datamind_kb_") for name in names)


def test_dataplane_scope_boundaries():
    authorize("kb_search", {"datamind.dataplane.read"})
    authorize("kb_add_text", {"datamind.dataplane.write"})
    authorize("memory_save", {"datamind.dataplane.write"})


def test_store_role_accepts_external_write_scope():
    from datamind_dataplane.context import DataPlaneContext

    request = RequestContext(tenant_id="tenant", profile_id="default", user_id="user")
    context = DataPlaneContext.from_claims(
        {"tenant_id": "tenant", "profile": "default", "agent_role": "store",
         "scope": "datamind.dataplane.external_write"},
        request,
    )
    assert context.role == "store"


def test_external_write_scope_cannot_pollute_memory_or_skills():
    scope = {"datamind.dataplane.external_write"}
    for tool in ("kb_add_text", "kb_ingest_document", "kb_ingest_path", "db_import_records", "graph_upsert_triples"):
        authorize(tool, scope)
    for tool in ("memory_save", "memory_forget", "skill_upsert", "kb_reindex"):
        with pytest.raises(AuthorizationError):
            authorize(tool, scope)


def test_profile_context_is_tenant_scoped():
    context = RequestContext(tenant_id="tenant-a", profile_id="project-a")
    assert context.tenant_id == "tenant-a"
    assert context.profile_id == "project-a"
