from fastapi import WebSocket

from websocket.repository import Repository


class ModerationManager:
    def __init__(self):
        self.active_connections : dict[int, WebSocket] = {} # interactive_id : WebSocket to leader

    async def connect(self, websocket: WebSocket, interactive_id: int):
        await websocket.accept()
        self.active_connections[interactive_id] = websocket

    async def broadcast(self, interactive_id:int):
        if interactive_id in self.active_connections:
            message = await Repository.get_moderation_data(interactive_id=interactive_id)
            try:
                await self.active_connections[interactive_id].send_json(message.model_dump())
            except:
                await self.disconnect(interactive_id=interactive_id)

    async def disconnect(self, interactive_id: int):
        if interactive_id in self.active_connections:
            ws = self.active_connections.pop(interactive_id)
            await ws.close()