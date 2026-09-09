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


class _System:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_ids = {"b"}

    async def ingest(self, prompt: str) -> dict:
        external_id = prompt.split('"external_id":"', 1)[1].split('"', 1)[0]
        self.calls.append(external_id)
        if external_id in self.fail_ids:
            self.fail_ids.remove(external_id)
            raise TimeoutError("simulated item timeout")
        return {"receipts": [{"receipt_id": f"receipt-{external_id}", "status": "stored"}]}


class _Runtime:
    def __init__(self, system: _System) -> None:
        self.bundle = type("Bundle", (), {"system": system})()

    async def get(self, _context):
        return self.bundle


def _batch() -> ExternalBatch:
    now = datetime.now(timezone.utc)
    return ExternalBatch(
        source=ExternalSource(provider="test", connection_id="c", resource_type="mail", stream="inbox"),
        items=[ExternalItem(external_id=item, updated_at=now, text=f"item {item}") for item in ("a", "b", "c")],
        confirm=True,
    )


async def _wait(service: ExternalIngestService) -> None:
    tasks = tuple(service._tasks.values())
    if tasks:
        await asyncio.gather(*tasks)


def test_item_receipts_survive_timeout_and_retry_skips_committed_items():
    async def run() -> None:
        system = _System()
        service = ExternalIngestService(_Runtime(system), InMemoryGatewayState())
        context = RequestContext(tenant_id="tenant", profile_id="default")
        batch = _batch()

        first = await service.submit(batch, context)
        await _wait(service)
        partial = await service.status(first["job_id"], context)
        assert partial["status"] == "partial"
        assert partial["succeeded_items"] == 2
        assert partial["failed_items"] == 1
        assert len(partial["receipts"]) == 2
        assert partial["checkpoint_committed"] is False
        assert system.calls == ["a", "b", "c"]

        await service.submit(batch, context)
        await _wait(service)
        completed = await service.status(first["job_id"], context)
        assert completed["status"] == "completed"
        assert completed["succeeded_items"] == 3
        assert completed["checkpoint_committed"] is True
        assert system.calls == ["a", "b", "c", "b"]
        await service.close()

    asyncio.run(run())
