from pydantic import BaseModel
from typing import Optional, List


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None


class CartItem(BaseModel):
    part_number: str
    name: str
    price: float
    quantity: int = 1


class CartState(BaseModel):
    items: List[CartItem] = []
    total: float = 0.0
