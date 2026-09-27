from datetime import datetime

from pydantic import BaseModel


class MessageBulk(BaseModel):
    messages: list[str]
    fetched_at: datetime


class Channel(BaseModel):
    id: str
    name: str
    messages: MessageBulk | None = None


class Server(BaseModel):
    id: str
    name: str
    channels: list[Channel] | None = None


class Bot(BaseModel):
    token: str
    servers: list[Server] | None = None

    def get_server_by_name(self, name):
        if self.servers is None:
            return None

        for server in self.servers:
            if server.name == name:
                return server
