import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/contracts/src"))
sys.path.insert(0, str(ROOT / "services/gateway/src"))

from datamind_contracts import ExternalBatch, ExternalItem, ExternalSource, RequestContext
from datamind_gateway.external_ingest import ExternalIngestService
from datamind_gateway.state import InMemoryGatewayState


def _batch() -> ExternalBatch:
    return ExternalBatch(
        source=ExternalSource(provider="test", connection_id="source", resource_type="records", stream="main"),
        items=[ExternalItem(external_id="one", updated_at=datetime.now(timezone.utc), text="hello")],
        checkpoint={"after": "cursor-1", "expected_version": 0},
        confirm=True,
    )


class _Bundle:
    def __init__(self, result):
        self.system = self
        self.result = result

    async def ingest(self, _prompt):
        return self.result


class _Runtime:
    def __init__(self, result):
        self.bundle = _Bundle(result)

    async def get(self, _context):
        return self.bundle


def test_empty_store_receipts_are_not_success():
    receipts, error = ExternalIngestService._receipts({"answer": "已完成"})
    assert receipts == []
    assert error == "store_agent_no_receipts"


def test_failed_nested_receipt_is_rejected():
    receipts, error = ExternalIngestService._receipts({
        "receipts": [{"receipt_id": "r1", "results": [{"status": "failed"}]}]
    })
    assert receipts and error == "store_agent_failed_receipt"


def test_empty_receipts_do_not_commit_checkpoint():
    async def run():
        state = InMemoryGatewayState()
        service = ExternalIngestService(_Runtime({"answer": "没有真正写入"}), state)
        context = RequestContext(tenant_id="tenant", profile_id="default")
        job_id = "job-test-empty-receipts"
        await state.create_job({
            "job_id": job_id, "status": "accepted", "tenant_id": context.tenant_id,
            "profile_id": context.profile_id, "receipts": [],
        })
        await service._run(job_id, _batch(), context, "test:source:records:main")
        job = await state.get_job(job_id)
        assert job["status"] == "failed"
        assert job["error"] == "store_agent_no_receipts"
        assert job["checkpoint_committed"] is False
        assert state.checkpoints == {}

    asyncio.run(run())
