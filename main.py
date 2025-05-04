from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    telegram_id: int
    username: str
    first_name: str
    last_name: str = None
    phone_number: str  = None

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    user = User(telegram_id=123, username=name, first_name=name)
    return {"message": user}

@app.websocket("/ws/{id_interactive}")
async def websocket_endpoint(websocket: WebSocket, id_interactive: int, telegram_id: int):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        active_connections.remove(websocket)
