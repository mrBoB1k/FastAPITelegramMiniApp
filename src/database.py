import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Base

# Определяем среду выполнения
# ENVIRONMENT = os.getenv("ENVIRONMENT")
#
# ENVIRONMENT="production"
#
# if ENVIRONMENT == "production":
#     print("делаю посгру")
#     # PostgreSQL для продакшена
#     DB_HOST = os.getenv("DB_HOST")  # имя сервиса в docker-compose
#     DB_PORT = os.getenv("DB_PORT")
#     DB_NAME = os.getenv("DB_NAME")
#     DB_USER = os.getenv("DB_USER")
#     DB_PASSWORD = os.getenv("DB_PASSWORD")
#
#     DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
# else:
#     # SQLite для разработки
#     print("делаю лайту")
#     DATABASE_FILE = "database.db"
#     DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE}"

DB_HOST = os.getenv("DB_HOST")  # имя сервиса в docker-compose
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False)
new_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)