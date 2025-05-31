from sqlalchemy import select, delete, and_
from database import new_session
from models import *
from datetime import datetime
from reports.schemas import TelegramId, PreviewInteractive, InteractiveList, ExportForAnalise
import random
import string
from typing import Optional, List, Any, Type, Coroutine


class Repository:
    @classmethod
    async def get_user_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
            user_id = result.scalar_one_or_none()
            return user_id

    @classmethod
    async def get_reports_preview(cls, user_id: int) -> InteractiveList:
        async with new_session() as session:
            participant_count_subq = (
                select(
                    QuizParticipant.interactive_id,
                    func.count(QuizParticipant.id).label('participant_count')
                )
                .group_by(QuizParticipant.interactive_id)
                .subquery()
            )
            query = (
                select(
                    Interactive.id,
                    Interactive.title,
                    Interactive.target_audience,
                    Interactive.date_completed,
                    Interactive.location,
                    participant_count_subq.c.participant_count
                )
                .join(
                    participant_count_subq,
                    Interactive.id == participant_count_subq.c.interactive_id,
                    isouter=True
                )
                .where(
                    Interactive.created_by_id == user_id,
                    Interactive.conducted == True
                )
                .order_by(Interactive.date_completed.desc())
            )

            result = await session.execute(query)
            interactives = result.all()

            return InteractiveList(interactives_list=[
                PreviewInteractive(
                    title=interactive.title,
                    participant_count=interactive.participant_count or 0,
                    target_audience=interactive.target_audience,
                    location=interactive.location,
                    date_completed=cls._format_date(interactive.date_completed),
                    interactive_id=interactive.id
                )
                for interactive in interactives
            ])

    @staticmethod
    def _format_date(date_obj: datetime | None) -> str | None:
        """Преобразует datetime в строку формата 'день.месяц.год' (23.05.25)"""
        if date_obj is None:
            return None
        return date_obj.strftime('%d.%m.%y')

    @classmethod
    async def get_interactive_export_for_analise(cls, interactive_id: int) -> list[ExportForAnalise]:
        async with new_session() as session:
            # 1. Получаем базовую информацию об интерактиве
            interactive = await session.get(Interactive, interactive_id)
            if not interactive:
                raise ValueError(f"Интерактив с ID {interactive_id} не найден")

            # 2. Получаем всех участников интерактива
            participants = await session.execute(
                select(QuizParticipant)
                .where(QuizParticipant.interactive_id == interactive_id)
            )
            participants = participants.scalars().all()

            if not participants:
                return []

            # 3. Собираем аналитику по каждому участнику
            analytics_data = []

            for participant in participants:
                # Получаем информацию о пользователе
                user = await session.get(User, participant.user_id)
                if not user:
                    continue

                # Считаем количество правильных ответов для участника
                correct_answers = await session.execute(
                    select(func.count())
                    .select_from(UserAnswer)
                    .join(Answer, UserAnswer.answer_id == Answer.id)
                    .where(
                        and_(
                            UserAnswer.participant_id == participant.id,
                            Answer.is_correct == True
                        )
                    )
                )
                correct_answers_count = correct_answers.scalar()

                # Собираем данные для экспорта
                analytics_data.append(ExportForAnalise(
                    interactive_id=interactive_id,
                    title=interactive.title,
                    date_completed=cls._format_date2(interactive.date_completed),
                    participant_count=len(participants),
                    question_count=await cls._get_question_count(session, interactive_id),
                    target_audience=interactive.target_audience,
                    location=interactive.location,
                    responsible_full_name=interactive.responsible_full_name,
                    telegram_id=user.telegram_id,
                    username=user.username,
                    full_name=f"{user.first_name} {user.last_name}" if user.last_name else user.first_name,
                    correct_answers_count=correct_answers_count
                ))

            return analytics_data

    @classmethod
    async def _get_question_count(cls, session, interactive_id: int) -> int:
        """Вспомогательный метод для подсчета вопросов"""
        result = await session.execute(
            select(func.count())
            .select_from(Question)
            .where(Question.interactive_id == interactive_id)
        )
        return result.scalar()

    @staticmethod
    def _format_date2(date_obj: datetime | None) -> str | None:
        """Преобразует datetime в строку формата 'день.месяц.год' (23.05.2025)"""
        if date_obj is None:
            return None
        return date_obj.strftime('%d.%m.%Y')