from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import URL_BACK,URL_FRONT
from database import init_db

# from users.router import router as user_router
from websocket.router import router as websocket_router
from interactivities.router import router as interactivity_router
from reports.router import router as report_router
from broadcasts.router import router as broadcast_router
from organizations.router import router as organization_router
from auth.router import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # инициализация БД при запуске (только если файла нет)
    yield


# app = FastAPI(dependencies=[Depends(verify_key)], lifespan=lifespan)
app = FastAPI(lifespan=lifespan)

origins = [
    URL_BACK,
    URL_FRONT
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Или ['*'] для всех / origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(user_router)
app.include_router(interactivity_router)
app.include_router(websocket_router)
app.include_router(report_router)
app.include_router(broadcast_router)
app.include_router(organization_router)
app.include_router(auth_router)
