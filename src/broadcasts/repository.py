from fastapi import HTTPException
from sqlalchemy import select

from database import new_session
from models import *

from minios3.schemas import ImageModel


class Repository:
    @classmethod
    async def get_telegram_id_for_interactive_id(cls, interactive_id: int, organization_id: int) -> list[int]:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive)
                .where(Interactive.id == interactive_id)
            )

            interactive = result.scalar_one_or_none()
            if interactive is None:
                raise HTTPException(status_code=404, detail=f"Интерактив с ID {interactive.id} не найден")

            organization = await session.execute(
                select(OrganizationParticipant.organization_id)
                .where(OrganizationParticipant.id == interactive.created_by_id)
            )
            organization = organization.scalar_one_or_none()
            if organization_id != organization:
                raise HTTPException(status_code=404, detail=f"Интерактив принадлежит другой организаций")

            participants = await session.execute(
                select(QuizParticipant)
                .where(QuizParticipant.interactive_id == interactive.id)
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
