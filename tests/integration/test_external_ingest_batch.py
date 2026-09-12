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


class _BatchRuntime:
    def __init__(self):
        self.calls = 0
        self.item_count = 0

    async def ingest_batch(self, _context, _message, *, external=False, final_contract=None):
        assert external is True
        assert final_contract and final_contract["type"] == "object"
        self.calls += 1
        self.item_count = 2
        return {
            "answer": '{"status":"completed","items":['
                      '{"source":"a","status":"completed","receipt_ids":["r-a"]},'
                      '{"source":"b","status":"completed","receipt_ids":["r-b"]}]}',
            "receipts": [
                {"receipt_id": "r-a", "status": "stored"},
                {"receipt_id": "r-b", "status": "stored"},
            ],
        }


def test_external_ingest_uses_one_store_agent_batch_call():
    async def run():
        now = datetime.now(timezone.utc)
        batch = ExternalBatch(
            source=ExternalSource(provider="test", connection_id="c", resource_type="mail", stream="inbox"),
            items=[ExternalItem(external_id="a", updated_at=now, text="one"),
                   ExternalItem(external_id="b", updated_at=now, text="two")],
            checkpoint={"after": "cursor-1", "expected_version": 0},
            confirm=True,
        )
        runtime = _BatchRuntime()
        state = InMemoryGatewayState()
        service = ExternalIngestService(runtime, state)
        context = RequestContext(tenant_id="tenant", profile_id="default")
        accepted = await service.submit(batch, context)
        await asyncio.gather(*tuple(service._tasks.values()))
        result = await service.status(accepted["job_id"], context)
        assert runtime.calls == 1
        assert result["status"] == "completed"
        assert result["succeeded_items"] == 2
        assert len(result["receipts"]) == 2
        assert result["checkpoint_committed"] is True
        await service.close()

    asyncio.run(run())
