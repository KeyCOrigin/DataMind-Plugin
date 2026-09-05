from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "datamind-dataplane"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready", "service": "datamind-dataplane"}
