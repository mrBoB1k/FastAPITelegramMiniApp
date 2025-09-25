from sqlalchemy import select, delete
from database import new_session
from models import *
from datetime import datetime
from interactivities.schemas import UserIdAndRole, InteractiveCreate, InteractiveId, InteractiveConducted, \
    Interactive as InteractiveFull, Answer as AnswerFull, Question as QuestionFull
import random
import string


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
    async def check_code_exists(cls, code: str) -> int:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive.id).where(Interactive.code == code, Interactive.conducted == False)
            )
            return result.scalar_one_or_none()

    @classmethod
    async def generate_unique_code(cls, length: int = 6) -> str:
        # Простой читаемый код: буквы и цифры, например AB123C
        alphabet = string.digits
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
                        is_correct=answer['is_correct']
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
            if conducted:
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
            else:
                query = (
                    select(
                        Interactive.id,
                        Interactive.title,
                        Interactive.target_audience,
                        Interactive.date_completed,
                        Interactive.created_at,
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
                    .order_by(Interactive.created_at.desc())
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
        return date_obj.strftime('%d.%m.%y')

    @classmethod
    async def get_all_interactive_info(cls, user_id: int, interactive_id: int) -> InteractiveFull | None:
        async with new_session() as session:
            interactive = await session.execute(
                select(Interactive)
                .where(
                    Interactive.id == interactive_id,
                    Interactive.created_by_id == user_id
                )
            )
            interactive = interactive.scalar_one_or_none()
            if interactive is None:
                return None

            questions_result = await session.execute(
                select(Question)
                .where(Question.interactive_id == interactive_id)
                .order_by(Question.position)
            )
            questions = questions_result.scalars().all()

            questions_data = []
            for question in questions:
                answers_result = await session.execute(
                    select(Answer)
                    .where(Answer.question_id == question.id)
                )
                answers = answers_result.scalars().all()

                answers_data = [
                    AnswerFull(
                        text=answer.text,
                        is_correct=answer.is_correct
                    )
                    for answer in answers
                ]

                questions_data.append(
                    QuestionFull(
                        text=question.text,
                        position=question.position,
                        answers=answers_data
                    )
                )

            return InteractiveFull(
                title=interactive.title,
                description=interactive.description,
                target_audience=interactive.target_audience,
                location=interactive.location,
                responsible_full_name=interactive.responsible_full_name,
                answer_duration=interactive.answer_duration,
                discussion_duration=interactive.discussion_duration,
                countdown_duration=interactive.countdown_duration,
                questions=questions_data
            )

    @classmethod
    async def get_interactive_conducted(cls, interactive_id: int, user_id: int) -> bool:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive.conducted).where(Interactive.id == interactive_id,
                                                    Interactive.created_by_id == user_id)
            )
            conducted = result.scalar_one_or_none()

            return conducted

    @classmethod
    async def update_interactive(
            cls,
            interactive_id: int,
            data: Interactive
    ) -> InteractiveId:
        async with new_session() as session:
            # 1. Получаем интерактив
            interactive = await session.get(Interactive, interactive_id)
            if not interactive:
                raise ValueError(f"Интерактив с ID {interactive_id} не найден")

            # 2. Удаляем все существующие ответы и вопросы
            # Сначала удаляем ответы (из-за foreign key constraint)
            await session.execute(
                delete(Answer)
                .where(Answer.question_id.in_(
                    select(Question.id)
                    .where(Question.interactive_id == interactive_id)
                ))
            )

            # Затем удаляем вопросы
            await session.execute(
                delete(Question)
                .where(Question.interactive_id == interactive_id)
            )

            # 3. Обновляем основные данные интерактива
            update_data = data.model_dump(exclude={"questions"})
            for key, value in update_data.items():
                setattr(interactive, key, value)

            # 4. Создаем новые вопросы и ответы
            for question_data in data.questions:
                new_question = Question(
                    interactive_id=interactive_id,
                    text=question_data.text,
                    position=question_data.position
                )
                session.add(new_question)
                await session.flush()  # Получаем ID нового вопроса

                for answer_data in question_data.answers:
                    new_answer = Answer(
                        question_id=new_question.id,
                        text=answer_data.text,
                        is_correct=answer_data.is_correct
                    )
                    session.add(new_answer)

            await session.commit()
            return InteractiveId(interactive_id=interactive_id)
