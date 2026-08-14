from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ConversationCreate(BaseModel):
    title: str | None = None


class MessageCreate(BaseModel):
    content: str


@router.get("/")
async def list_conversations() -> dict:
    return {"items": []}


@router.post("/")
async def create_conversation(payload: ConversationCreate) -> dict:
    return {"id": "conv_placeholder", "title": payload.title, "status": "created"}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    return {"id": conversation_id, "messages": []}


@router.post("/{conversation_id}/messages")
async def send_message(conversation_id: str, payload: MessageCreate) -> dict:
    return {
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": f"Received: {payload.content}",
    }
