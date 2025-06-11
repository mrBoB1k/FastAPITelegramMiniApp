from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db

from users.router import router as user_router
from websocket.router import router as websocket_router
from interactivities.router import router as interactivity_router
from reports.router import router as report_router
from broadcasts.router import router as broadcast_router

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from dotenv import load_dotenv
import os

load_dotenv()
_SECRET_KEY = os.getenv('SECRET_KEY')


async def verify_key(x_key: str):
    if x_key != _SECRET_KEY:
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
app.include_router(report_router)
app.include_router(broadcast_router)
