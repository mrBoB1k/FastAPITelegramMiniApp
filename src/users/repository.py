from sqlalchemy import select, delete
from database import new_session
from users.schemas import UserRegister, UserRoleEnum, UsersChangeRole, UsersBase
from models import *


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

    @classmethod
    async def get_interactive_count_by_user_id(cls, user_id: int) -> int:
        async with new_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(Interactive)
                .where(Interactive.created_by_id == user_id)
            )
            return result.scalar_one()

    @classmethod
    async def get_all_interactive_id(cls, user_id: int) -> list[int]:
        async with new_session() as session:
            query = (
                select(Interactive.id)
                .where(Interactive.created_by_id == user_id)
            )

            result = await session.execute(query)
            interactive_ids = result.scalars().all()

            return list(interactive_ids)

    @classmethod
    async def get_all_quiz_participants_id(cls, user_id: int) -> list[int]:
        async with new_session() as session:
            query = (
                select(QuizParticipant.id)
                .where(QuizParticipant.user_id == user_id)
            )

            result = await session.execute(query)
            quiz_participants_id = result.scalars().all()

            return list(quiz_participants_id)

    @classmethod
    async def delete_quiz_participant_and_answers(cls, quiz_participant_id: int) -> bool:
        async with new_session() as session:
            async with session.begin():
                # Удаляем все ответы участника
                delete_answers_query = (
                    delete(UserAnswer)
                    .where(UserAnswer.participant_id == quiz_participant_id)
                )
                await session.execute(delete_answers_query)

                # Удаляем участника
                delete_participant_query = (
                    delete(QuizParticipant)
                    .where(QuizParticipant.id == quiz_participant_id)
                )
                result = await session.execute(delete_participant_query)

                # Возвращаем True если участник был удален, False если не найден
                return result.rowcount > 0

    @classmethod
    async def delete_user(cls, user_id: int) -> bool:
        async with new_session() as session:
            async with session.begin():
                delete_query = (
                    delete(User)
                    .where(User.id == user_id)
                )

                result = await session.execute(delete_query)
                # Возвращаем True если пользователь был удален, False если не найден
                return result.rowcount > 0
