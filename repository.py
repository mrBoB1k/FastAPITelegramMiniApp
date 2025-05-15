from sqlalchemy import select
from database import new_session
from schemas import UserRegister, UserRoleEnum, TelegramId
from models import *
from datetime import datetime


class Repository:
    @classmethod
    async def register_user(cls, data: UserRegister) -> UserRoleEnum:
        async with new_session() as session:
            user_dict = data.model_dump()

            user_dict["role"] = "participant"

            task = User(**user_dict)
            session.add(task)

            await session.flush()
            await session.commit()
            return task.role

    @classmethod
    async def get_role_by_telegram_id(cls, telegram_id: int) -> UserRoleEnum | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.role).where(User.telegram_id == telegram_id)
            )
            role = result.scalar_one_or_none()
            return role
