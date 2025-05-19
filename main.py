from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from users.router import router as user_router
from websocket.router import router as websocket_router
from interactivities.router import router as interactivity_router
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse


async def verify_key(x_key: str):
    if x_key != "super-secret-key":
        raise HTTPException(status_code=400, detail="X-Key header invalid")
    return x_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # инициализация БД при запуске (только если файла нет)
    yield


app = FastAPI(dependencies=[Depends(verify_key)], lifespan=lifespan)

origins = [
    "http://217.114.14.123:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],  # Или ['*'] для всех / origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/leader")
async def get_leader(request: Request):
    return templates.TemplateResponse("leader.html", {"request": request})

@app.get("/participant")
async def get_participant(request: Request):
    return templates.TemplateResponse("participant.html", {"request": request})

app.include_router(user_router)
app.include_router(interactivity_router)
app.include_router(websocket_router)

# html = """
# <!DOCTYPE html>
# <html>
#     <head>
#         <title>Chat</title>
#     </head>
#     <body>
#         <h1>WebSocket Chat</h1>
#         <h2>Your ID: <span id="ws-id"></span></h2>
#         <form action="" onsubmit="sendMessage(event)">
#             <input type="text" id="messageText" autocomplete="off"/>
#             <button>Send</button>
#         </form>
#         <ul id='messages'>
#         </ul>
#         <script>
#             var client_id = Date.now()
#             document.querySelector("#ws-id").textContent = client_id;
#             var ws = new WebSocket(`wss://${location.host}/ws/${client_id}`);
#             ws.onmessage = function(event) {
#                 var messages = document.getElementById('messages')
#                 var message = document.createElement('li')
#                 var content = document.createTextNode(event.data)
#                 message.appendChild(content)
#                 messages.appendChild(message)
#             };
#             function sendMessage(event) {
#                 var input = document.getElementById("messageText")
#                 ws.send(input.value)
#                 input.value = ''
#                 event.preventDefault()
#             }
#         </script>
#     </body>
# </html>
# """
#
#
# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: list[WebSocket] = []
#         self.time_task: asyncio.Task | None = None
#         self.time_task_running: bool = False
#
#     async def connect(self, websocket: WebSocket):
#         await websocket.accept()
#         self.active_connections.append(websocket)
#
#     def disconnect(self, websocket: WebSocket):
#         if websocket in self.active_connections:
#             self.active_connections.remove(websocket)
#
#     async def send_personal_message(self, message: str, websocket: WebSocket):
#         await websocket.send_text(message)
#
#     async def broadcast(self, message: str):
#         for connection in self.active_connections:
#             await connection.send_text(message)
#
#     async def start_time_broadcast(self):
#         self.time_task_running = True
#
#         async def send_time():
#             while self.time_task_running:
#                 current_time = datetime.now().strftime("%H:%M:%S")
#                 await self.broadcast(f"[TIME] {current_time}")
#                 await asyncio.sleep(1)
#
#         self.time_task = asyncio.create_task(send_time())
#
#     def stop_time_broadcast(self):
#         self.time_task_running = False
#         if self.time_task:
#             self.time_task.cancel()
#             self.time_task = None
#
#
# manager = ConnectionManager()
#
#
# @app.get("/")
# async def get():
#     return HTMLResponse(html)
#
#
# @app.websocket("/ws/{client_id}")
# async def websocket_endpoint(websocket: WebSocket, client_id: int):
#     await manager.connect(websocket)
#     try:
#         # Отправляем сообщение сразу после подключения
#         await manager.send_personal_message("Ты получаешь сообщение сразу как зайдёшь", websocket)
#
#         while True:
#             data = await websocket.receive_text()
#             if data.strip() == "/time start":
#                 if not manager.time_task_running:
#                     await manager.broadcast(f"Client #{client_id} started the clock.")
#                     await manager.start_time_broadcast()
#                 else:
#                     await manager.send_personal_message("Clock is already running.", websocket)
#             elif data.strip() == "/time stop":
#                 if manager.time_task_running:
#                     manager.stop_time_broadcast()
#                     await manager.broadcast(f"Client #{client_id} stopped the clock.")
#                 else:
#                     await manager.send_personal_message("Clock is not running.", websocket)
#             else:
#                 await manager.send_personal_message(f"You wrote: {data}", websocket)
#                 await manager.broadcast(f"Client #{client_id} says: {data}")
#     except WebSocketDisconnect:
#         manager.disconnect(websocket)
#         await manager.broadcast(f"Client #{client_id} left the chat")
#
# class User(BaseModel):
#     telegram_id: int
#     username: str
#     first_name: str
#     last_name: str = None
#     phone_number: str  = None
#
# @app.get("/hello")
# async def root():
#     return {"message": "Hello World"}
#
# @app.get("/hello/{name}")
# async def say_hello(name: str):
#     user = User(telegram_id=123, username=name, first_name=name)
#     return {"message": user}
#
#
# @app.websocket("/ws/{id_interactive}")
# async def websocket_endpoint(websocket: WebSocket, id_interactive: int, telegram_id: int):
#     await websocket.accept()
#     while True:
#         data = await websocket.receive_text()
#         await websocket.send_text(f"Message text was: {data}")
