from sqlalchemy import select
from database import new_session
from models import *
from fastapi import HTTPException

from minios3.schemas import ImageModel

class Repository:
    @classmethod
    async def get_user_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id, User.role == UserRole.leader)
            )
            user_id = result.scalar_one_or_none()
            return user_id

    @classmethod
    async def get_telegram_id_for_interactive_id(cls, interactive_id: int, user_id: int) -> list[int]:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive.id)
                .where(Interactive.id==interactive_id, Interactive.created_by_id==user_id)
            )

            interactive_id = result.scalar_one_or_none()
            if not interactive_id:
                raise HTTPException(status_code=404, detail=f"Интерактив с ID {interactive_id} не найден")

            participants = await session.execute(
                select(QuizParticipant)
                .where(QuizParticipant.interactive_id == interactive_id)
            )
            participants = participants.scalars().all()

            if not participants:
                return []

            data = []

            for participant in participants:
                # Получаем информацию о пользователе
                user = await session.get(User, participant.user_id)
                if not user:
                    continue

                data.append(user.telegram_id)

            return data

    @classmethod
    async def save_image(cls, data: ImageModel) -> int:
        async with new_session() as session:
            async with session.begin():
                new_image = Image(
                    filename=data.filename,
                    unique_filename=data.unique_filename,
                    content_type=data.content_type,
                    size=data.size,
                    bucket_name=data.bucket_name
                )

                session.add(new_image)
                await session.flush()

                return new_image.id
