import pytz
from sqlalchemy import select, and_
from database import new_session
from models import *
from datetime import datetime
from reports.schemas import PreviewInteractive, InteractiveList, ExportForAnalise, ExportForLeaderData, \
    ExportForLeaderHeader, ExportForLeaderBody, QuestionForLeaderHeader, AnswerForLeaderHeader, ParticipantAnswer, \
    DateTitleSH
from fastapi import HTTPException


class Repository:
    @classmethod
    async def get_user_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
            user_id = result.scalar_one_or_none()
            return user_id

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
                raise HTTPException(status_code=404, detail=f"Интерактив с ID {interactive_id} не найден")

            responsible_full_name = await session.get(OrganizationParticipant, interactive.created_by_id)
            if not responsible_full_name:
                raise HTTPException(status_code=404, detail="Не найден создатель интерактива")
            responsible_full_name = responsible_full_name.name

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
                correct_answers_count = await session.scalar(
                    select(func.count(UserAnswer.id))
                    .where(
                        UserAnswer.participant_id == participant.id,
                        UserAnswer.is_correct == True
                    )
                )

                # Получаем время ответов участника
                total_time = f"{participant.total_time // 60}:{participant.total_time % 60:02d}"

                # Получаем сумму баллов за правильные ответы участника
                stmt = (
                    select(func.coalesce(func.sum(Question.score), 0))
                    .select_from(UserAnswer)
                    .join(Question, UserAnswer.question_id == Question.id)
                    .where(
                        UserAnswer.participant_id == participant.id,
                        UserAnswer.is_correct == True
                    )
                )

                result = await session.scalar(stmt)
                total_score = result or 0

                # Собираем данные для экспорта
                analytics_data.append(ExportForAnalise(
                    interactive_id=interactive_id,
                    title=interactive.title,
                    date_completed=cls._format_date2(interactive.date_completed),
                    participant_count=len(participants),
                    question_count=await cls._get_question_count(session, interactive_id),
                    target_audience=interactive.target_audience,
                    location=interactive.location,
                    responsible_full_name=responsible_full_name,
                    telegram_id=user.telegram_id,
                    username=user.username,
                    full_name=f"{user.first_name} {user.last_name}" if user.last_name else user.first_name,
                    correct_answers_count=correct_answers_count,
                    total_time=total_time,
                    total_score=total_score,
                ))

            analytics_data.sort(key=lambda x: (-x.total_score, x.total_time))

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

        utc_time = pytz.UTC.localize(date_obj)
        yekat_time = utc_time.astimezone(pytz.timezone('Asia/Yekaterinburg'))\

        return yekat_time.strftime('%d.%m.%Y')

    @staticmethod
    def _format_date3(date_obj: datetime | None) -> str | None:
        """Преобразует datetime в строку формата 'день.месяц.год' (23.05.2025)"""
        if date_obj is None:
            return None

        utc_time = pytz.UTC.localize(date_obj)
        yekat_time = utc_time.astimezone(pytz.timezone('Asia/Yekaterinburg'))

        return yekat_time.strftime('%d.%m.%Y_%H-%M')

    @classmethod
    async def get_export_for_leader(cls, interactive_id: int) -> ExportForLeaderData:
        async with new_session() as session:
            # 1. Получаем информацию об интерактиве
            interactive = await session.get(Interactive, interactive_id)
            if not interactive:
                raise ValueError(f"Интерактив с ID {interactive_id} не найден")

            responsible_full_name = await session.get(OrganizationParticipant, interactive.created_by_id)
            if not responsible_full_name:
                raise HTTPException(status_code=404, detail="Не найден создатель интерактива")
            responsible_full_name = responsible_full_name.name

            # 2. Получаем всех участников
            participants = await session.execute(
                select(QuizParticipant)
                .where(QuizParticipant.interactive_id == interactive_id)
            )
            participants = participants.scalars().all()

            # 3. Получаем все вопросы и ответы для интерактива
            questions_result = await session.execute(
                select(Question)
                .where(Question.interactive_id == interactive_id)
                .order_by(Question.position)
            )
            questions = questions_result.scalars().all()

            # 4. Формируем header
            questions_data = []
            for question in questions:
                answers_result = await session.execute(
                    select(Answer)
                    .where(Answer.question_id == question.id)
                )
                answers = answers_result.scalars().all()

                answers_data = [
                    AnswerForLeaderHeader(
                        id=answer.id,
                        text=answer.text,
                        is_correct=answer.is_correct
                    )
                    for answer in answers
                ]

                questions_data.append(
                    QuestionForLeaderHeader(
                        id=question.id,
                        position=question.position,
                        text=question.text,
                        type=question.type,
                        score=question.score,
                        answers=answers_data
                    )
                )

            header = ExportForLeaderHeader(
                title=interactive.title,
                interactive_id=interactive.id,
                date_completed=cls._format_date(interactive.date_completed),
                participant_count=len(participants),
                target_audience=interactive.target_audience,
                location=interactive.location,
                responsible_full_name=responsible_full_name,
                question=questions_data
            )

            # 5. Формируем body с ответами участников
            body_data = []
            for participant in participants:
                user = await session.get(User, participant.user_id)
                if not user:
                    continue

                # Получаем все ответы участника
                user_answers_result = await session.execute(
                    select(UserAnswer)
                    .where(UserAnswer.participant_id == participant.id)
                )
                user_answers = user_answers_result.scalars().all()

                # Считаем правильные ответы
                correct_answers = 0
                participant_answers = []
                for ua in user_answers:
                    if ua.is_correct:
                        correct_answers += 1

                    answer_id = None
                    if ua.answer_type == 'text':
                        answer_id = ua.text_answer
                    if ua.answer_type == 'one':
                        answer_id = ua.selected_answer_ids[0]
                    if ua.answer_type == 'many':
                        answer_id = ua.selected_answer_ids

                    time = f"{ua.time // 60}:{ua.time % 60:02d}"
                    participant_answers.append(
                        ParticipantAnswer(
                            question_id=ua.question_id,
                            answer_id=answer_id,
                            time=time,
                            is_correct=ua.is_correct,
                        )
                    )

                # Формируем полное имя
                full_name = user.first_name
                if user.last_name:
                    full_name += f" {user.last_name}"

                # Получаем время ответов участника
                total_time = f"{participant.total_time // 60}:{participant.total_time % 60:02d}"

                # Получаем сумму баллов за правильные ответы участника
                stmt = (
                    select(func.coalesce(func.sum(Question.score), 0))
                    .select_from(UserAnswer)
                    .join(Question, UserAnswer.question_id == Question.id)
                    .where(
                        UserAnswer.participant_id == participant.id,
                        UserAnswer.is_correct == True
                    )
                )

                result = await session.scalar(stmt)
                total_score = result or 0

                body_data.append(
                    ExportForLeaderBody(
                        telegram_id=user.telegram_id,
                        username=user.username,
                        full_name=full_name,
                        correct_answers_count=correct_answers,
                        total_time=total_time,
                        total_score=total_score,
                        answers=participant_answers
                    )
                )

            body_data.sort(key= lambda x: (-x.total_score, x.total_time))

            return ExportForLeaderData(
                header=header,
                body=body_data
            )

    @classmethod
    async def get_title_and_date_for_interactive(cls, interactive_id: int) -> DateTitleSH | None:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive).where(Interactive.id == interactive_id)
            )
            data = result.scalar_one_or_none()
            if data is not None:
                return DateTitleSH(title=data.title, date_completed=cls._format_date3(data.date_completed))
            return data



    @classmethod
    async def check_user_conducted_interactive(cls, organization_id: int, interactive_id: int) -> bool:
        async with new_session() as session:
            query = (
                select(Interactive)
                .where(
                    Interactive.id == interactive_id,
                    Interactive.conducted == True
                )
            )

            result = await session.execute(query)
            interactive = result.scalar_one_or_none()
            if interactive is None:
                return False

            organization = await session.execute(
                select(OrganizationParticipant.organization_id)
                .where(OrganizationParticipant.id == interactive.created_by_id)
            )
            organization = organization.scalar_one_or_none()
            if organization is None:
                return False

            return True