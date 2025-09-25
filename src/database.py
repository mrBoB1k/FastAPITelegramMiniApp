import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Base

DATABASE_FILE = "database.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE}"

engine = create_async_engine(DATABASE_URL, echo=False)
new_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    if not os.path.exists("database.db"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
