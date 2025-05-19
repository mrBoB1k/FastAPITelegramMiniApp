from sqlalchemy import select
from database import new_session
from users.schemas import UserRegister, UserRoleEnum, TelegramId, UsersChangeRole, UsersBase
from models import *
from datetime import datetime


class Repository:
    @classmethod
    async def register_user(cls, data: UserRegister) -> UserRoleEnum:
        async with new_session() as session:
            user_dict = data.model_dump()

            user_dict["role"] = "participant"

            user = User(**user_dict)
            session.add(user)

            await session.flush()
            await session.commit()
            return user.role

    @classmethod
    async def get_role_by_telegram_id(cls, telegram_id: int) -> UserRoleEnum | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.role).where(User.telegram_id == telegram_id)
            )
            role = result.scalar_one_or_none()
            return role

    @classmethod
    async def change_role(cls, data: UsersChangeRole) -> UsersBase:
        async with new_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == data.telegram_id)
            )
            user = result.scalar_one_or_none()

            user.role = data.role
            await session.commit()
            await session.refresh(user)

            return user