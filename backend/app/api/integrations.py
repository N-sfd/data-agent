from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class IntegrationConnect(BaseModel):
    provider: str
    credentials: dict[str, str] | None = None


@router.get("/")
async def list_integrations() -> dict:
    return {"items": []}


@router.post("/connect")
async def connect_integration(payload: IntegrationConnect) -> dict:
    return {"provider": payload.provider, "status": "connected"}


@router.delete("/{provider}")
async def disconnect_integration(provider: str) -> dict:
    return {"provider": provider, "status": "disconnected"}
