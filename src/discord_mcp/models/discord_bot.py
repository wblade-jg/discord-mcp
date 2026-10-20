from datetime import datetime

from pydantic import BaseModel


class Message(BaseModel):
    content: str


class MessageBulk(BaseModel):
    messages: list[Message] | None = None
    fetched_at: datetime | None = None
    ttl: int = 5


class Channel(BaseModel):
    id: str
    name: str
    messages: MessageBulk | None = None


class Server(BaseModel):
    id: str
    name: str
    channels: list[Channel] | None = None
