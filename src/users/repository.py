from sqlalchemy import select, delete
from database import new_session
from users.schemas import UserRegister
from models import *


class Repository:
    @classmethod
    async def register_user(cls, data: UserRegister) -> User:
        async with new_session() as session:
            user_dict = data.model_dump()

            user = User(**user_dict)
            session.add(user)

            await session.flush()
            await session.commit()
            return user

    @classmethod
    async def get_user_id_by_telegram_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
            role = result.scalar_one_or_none()
            return role
