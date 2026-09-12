from __future__ import annotations

import json
from typing import Any

from datamind_contracts import StoreBatchRequest, StoreBatchResult
from .auth import require_scope
from .prompts import BATCH_FINAL_CONTRACT, build_store_batch_request, build_store_request
from .tenancy import context_from_claims


async def retrieve(runtime, claims: dict, args: dict):
    require_scope(claims, "datamind:retrieve")
    context = context_from_claims(claims, args)
    return await (await runtime.get(context)).system.query(str(args.get("message") or ""))


async def store(runtime, claims: dict, args: dict):
    require_scope(claims, "datamind:store")
    if args.get("confirm") is not True:
        raise PermissionError("datamind_agent_store requires confirm=true")
    source_trust = args.get("source_trust", "internal")
    if source_trust not in {"internal", "external"}:
        raise ValueError("source_trust must be internal or external")
    context = context_from_claims(claims, args)
    external = source_trust == "external"
    return await runtime.ingest(
        context,
        build_store_request(str(args.get("message") or ""), external=external),
        external=external,
    )


def _parse_json_answer(answer: Any) -> dict[str, Any]:
    if not isinstance(answer, str):
        raise ValueError("store_agent_batch_invalid_answer")
    text = answer.strip()
    fenced = text.split("```", 2)
    if len(fenced) == 3:
        text = fenced[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError("store_agent_batch_invalid_json") from exc
    if not isinstance(value, dict):
        raise ValueError("store_agent_batch_result_must_be_object")
    return value


def _normalize_batch_result(raw: Any, request: StoreBatchRequest) -> dict[str, Any]:
    """Bind model-reported item ids to actual DataPlane receipts."""
    if not isinstance(raw, dict):
        raise ValueError("store_agent_batch_missing_result")
    receipt_pool = {
        str(item.get("receipt_id")): item
        for item in (raw.get("receipts") or [])
        if isinstance(item, dict) and str(item.get("receipt_id") or "")
    }
    # Older loop implementations return receipts only at the outer level.
    # A batch item must explicitly name its receipts in the final contract;
    # this prevents a successful receipt from being attributed to another item.
    raw_items = raw.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("store_agent_batch_missing_items")
    expected = {item.source for item in request.items}
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "")
        if source not in expected or source in seen:
            continue
        seen.add(source)
        ids = item.get("receipt_ids")
        if not isinstance(ids, list):
            ids = [value.get("receipt_id") for value in item.get("receipts", [])
                   if isinstance(value, dict)] if isinstance(item.get("receipts"), list) else []
        receipts = [receipt_pool[str(receipt_id)] for receipt_id in ids if str(receipt_id) in receipt_pool]
        receipt_failed = any(
            receipt.get("status") == "failed"
            or any(isinstance(entry, dict) and entry.get("status") == "failed"
                   for entry in (receipt.get("results") or []))
            for receipt in receipts
        )
        status = "completed" if item.get("status") == "completed" and receipts and not receipt_failed else "failed"
        normalized.append({
            "source": source,
            "status": status,
            "receipts": receipts,
            "error": None if status == "completed" else str(item.get("error") or "missing_or_invalid_receipt"),
        })
    for request_item in request.items:
        if request_item.source not in seen:
            normalized.append({
                "source": request_item.source,
                "status": "failed",
                "receipts": [],
                "error": "store_agent_batch_missing_item_result",
            })
    completed = sum(item["status"] == "completed" for item in normalized)
    status = "completed" if completed == len(request.items) else "partial" if completed else "failed"
    return StoreBatchResult(
        status=status,
        items=normalized,
        receipts=[receipt for item in normalized for receipt in item["receipts"]],
        error=str(raw.get("error")) if raw.get("error") else None,
    ).model_dump()


async def store_batch(runtime, claims: dict, args: dict):
    require_scope(claims, "datamind:store")
    request = StoreBatchRequest.model_validate(args)
    if request.confirm is not True:
        raise PermissionError("datamind_agent_store_batch requires confirm=true")
    if len({item.source for item in request.items}) != len(request.items):
        raise ValueError("datamind_agent_store_batch requires unique item.source values")
    context = context_from_claims(claims, args)
    external = request.source_trust == "external"
    payload = [item.model_dump(exclude_none=True) for item in request.items]
    result = await runtime.ingest_batch(
        context,
        build_store_batch_request(payload, external=external),
        external=external,
        final_contract=BATCH_FINAL_CONTRACT,
    )
    # Keep actual receipts outside the model's prose contract so the Gateway
    # can reject hallucinated receipt ids.
    return _normalize_batch_result({
        **(_parse_json_answer(result.get("answer")) if isinstance(result, dict) else {}),
        "receipts": result.get("receipts", []) if isinstance(result, dict) else [],
    }, request)
