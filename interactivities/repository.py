from sqlalchemy import select
from database import new_session
from models import *
from datetime import datetime
from interactivities.schemas import UserIdAndRole, InteractiveCreate, InteractiveId, InteractiveConducted
import random
import string
from typing import Optional


class Repository:
    @classmethod
    async def get_user_id_and_role_by_telegram_id(cls, telegram_id: int) -> UserIdAndRole | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id, User.role).where(User.telegram_id == telegram_id)
            )
            row = result.one_or_none()
            if row is None:
                return None
            user_id, role = row
            return UserIdAndRole(user_id=user_id, role=role)

    @classmethod
    async def check_code_exists(cls, code: str) -> bool:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive.id).where(Interactive.code == code)
            )
            return result.scalar_one_or_none() is not None

    @classmethod
    async def generate_unique_code(cls, length: int = 6) -> str:
        # Простой читаемый код: буквы и цифры, например AB123C
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(alphabet, k=length))
            if not await cls.check_code_exists(code):
                return code

    @classmethod
    async def create_interactive(cls, data: InteractiveCreate) -> InteractiveId:
        async with new_session() as session:
            interactive_full_dict = data.model_dump()
            questions_list = interactive_full_dict.pop('questions')
            interactive_dict = interactive_full_dict

            new_interactive = Interactive(**interactive_dict)
            session.add(new_interactive)
            await session.flush()

            for question in questions_list:
                new_question = Question(
                    interactive_id=new_interactive.id,
                    text=question['text'],
                    position=question['position']
                )
                session.add(new_question)
                await session.flush()

                for answer in question['answers']:
                    new_answer = Answer(
                        question_id=new_question.id,
                        text=answer['text'],
                        is_correct=answer['is_answered']
                    )
                    session.add(new_answer)
                    await session.flush()

            await session.commit()
            return InteractiveId(interactive_id=new_interactive.id)

    @classmethod
    async def get_user_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
            user_id = result.scalar_one_or_none()
            return user_id

    @classmethod
    async def get_interactives(cls, user_id: int, conducted: bool) -> list[InteractiveConducted]:
        async with new_session() as session:
            question_count_subq = (
                select(
                    Question.interactive_id,
                    func.count(Question.id).label('question_count')
                )
                .group_by(Question.interactive_id)
                .subquery()
            )

            query = (
                select(
                    Interactive.id,
                    Interactive.title,
                    Interactive.target_audience,
                    Interactive.date_completed,
                    question_count_subq.c.question_count
                )
                .join(
                    question_count_subq,
                    Interactive.id == question_count_subq.c.interactive_id,
                    isouter=True
                )
                .where(
                    Interactive.created_by_id == user_id,
                    Interactive.conducted == conducted
                )
                .order_by(Interactive.date_completed.desc())
            )

            result = await session.execute(query)
            interactives = result.all()

            return [
                InteractiveConducted(
                    id=interactive.id,
                    title=interactive.title,
                    target_audience=interactive.target_audience,
                    question_count=interactive.question_count or 0,
                    date_completed=cls._format_date(interactive.date_completed)
                )
                for interactive in interactives
            ]

    @staticmethod
    def _format_date(date_obj: datetime | None) -> str | None:
        """Преобразует datetime в строку формата 'день.месяц.год' (23.05.25)"""
        if date_obj is None:
            return None
        return date_obj.strftime('%d.%m.%Y')
