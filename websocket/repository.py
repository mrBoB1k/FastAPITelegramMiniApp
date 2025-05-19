from sqlalchemy import select, exists, desc
from database import new_session
from models import *
from datetime import datetime
from sqlalchemy.sql import label
from websocket.schemas import InteractiveInfo, Question as QuestionSchema, CreateQuizParticipant, PutUserAnswers, \
    Percentage, Answer as AnswerSchema, Winner


class Repository:
    @classmethod
    async def check_interactive_creates(cls, interactive_id: int, user_id: int) -> bool:
        async with new_session() as session:
            result = await session.execute(
                select(
                    exists().where(
                        Interactive.id == interactive_id,
                        Interactive.created_by_id == user_id,
                    )
                )
            )
            return result.scalar()

    @classmethod
    async def check_interactive(cls, interactive_id: int) -> bool:
        async with new_session() as session:
            result = await session.execute(
                select(
                    exists().where(
                        Interactive.id == interactive_id
                    )
                )
            )
            return result.scalar()

    @classmethod
    async def get_user_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
            user_id = result.scalar_one_or_none()
            return user_id

    @classmethod
    async def get_interactive_info(cls, interactive_id: int) -> InteractiveInfo:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive).where(Interactive.id == interactive_id)
            )
            interactive = result.scalar_one_or_none()

            return InteractiveInfo(interactive_id=interactive.id,
                                   code=interactive.code,
                                   title=interactive.title,
                                   description=interactive.description,
                                   answer_duration=interactive.answer_duration,
                                   discussion_duration=interactive.discussion_duration,
                                   countdown_duration=interactive.countdown_duration)

    @classmethod
    async def get_interactive_conducted(cls, interactive_id: int) -> bool:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive.conducted).where(Interactive.id == interactive_id)
            )
            conducted = result.scalar_one_or_none()

            return conducted

    @classmethod
    async def get_interactive_question(cls, interactive_id: int) -> list[QuestionSchema]:
        async with new_session() as session:
            result = await session.execute(
                select(Question)
                .where(Question.interactive_id == interactive_id)
                .order_by(Question.position)
            )

            questions = result.scalars().all()
            return [
                QuestionSchema(id=q.id, text=q.text, position=q.position)
                for q in questions
            ]

    @classmethod
    async def get_question_answers(cls, question_id: int) -> list[AnswerSchema]:
        async with new_session() as session:
            result = await session.execute(
                select(Answer)
                .where(Answer.question_id == question_id)
            )

            answers = result.scalars().all()
            return [
                AnswerSchema(id=a.id, text=a.text)
                for a in answers
            ]

    @classmethod
    async def get_correct_answer(cls, question_id: int) -> int:
        async with new_session() as session:
            result = await session.execute(
                select(Answer.id)
                .where(Answer.question_id == question_id and Answer.is_correct)
            )

            answer_id = result.scalar()
            return answer_id

    @classmethod
    async def register_quiz_participant(cls, data: CreateQuizParticipant) -> int:
        async with new_session() as session:
            participant_dict = data.model_dump()

            participant = QuizParticipant(**participant_dict)
            session.add(participant)

            await session.flush()
            await session.commit()
            return participant.id

    @classmethod
    async def put_user_answers(cls, data: PutUserAnswers):
        async with new_session() as session:
            # answer_dict = data.model_dump()

            fllag_answer = await session.execute(
                select(UserAnswer)
                .where(UserAnswer.participant_id == data.participant_id and UserAnswer.question_id == data.question_id)
            )

            fllag_answer = fllag_answer.scalar_one_or_none()
            if fllag_answer is None:
                answer_dict = data.model_dump()
                user_answer = UserAnswer(**answer_dict)
                session.add(user_answer)
                await session.flush()
                await session.commit()
            else:
                fllag_answer.answer_id = data.answer_id
                await session.commit()
                await session.refresh(fllag_answer)

    @classmethod
    async def get_percentages(cls, question_id: int) -> list[Percentage]:
        async with new_session() as session:
            total_stmt = select(func.count()).where(UserAnswer.question_id == question_id)
            total = await session.scalar(total_stmt)

            if total == 0:
                return []

            # Количество ответов по каждому answer_id
            stmt = (
                select(UserAnswer.answer_id, func.count().label("count"))
                .where(UserAnswer.question_id == question_id)
                .group_by(UserAnswer.answer_id)
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                Percentage(
                    id=row.answer_id,
                    percentage=(row.count / total) * 100
                )
                for row in rows
            ]

    @classmethod
    async def mark_interactive_conducted(cls, interactive_id: int):
        async with new_session() as session:
            interactive = await session.get(Interactive, interactive_id)
            if interactive:
                interactive.conducted = True
                await session.commit()

    @classmethod
    async def get_winners(cls, interactive_id: int) -> list[Winner]:
        async with new_session() as session:
            subquery = (
                select(
                    QuizParticipant.id.label("participant_id"),
                    QuizParticipant.user_id.label("user_id")
                )
                .where(QuizParticipant.interactive_id == interactive_id)
                .subquery()
            )

            # Подсчёт правильных ответов по user_id
            correct_answers = (
                select(
                    subquery.c.user_id,
                    func.count(UserAnswer.id).label("correct_count")
                )
                .join(UserAnswer, UserAnswer.participant_id == subquery.c.participant_id)
                .join(Answer, Answer.id == UserAnswer.answer_id)
                .where(Answer.is_correct == True)
                .group_by(subquery.c.user_id)
                .order_by(desc("correct_count"))
                .limit(3)
                .subquery()
            )

            # Получаем username + количество правильных ответов
            result = await session.execute(
                select(
                    User.username,
                    correct_answers.c.correct_count
                ).join(User, User.id == correct_answers.c.user_id)
                .order_by(desc(correct_answers.c.correct_count))
            )
            rows = result.fetchall()

            winners = [Winner(position=i + 1, username=row) for i, row in enumerate(rows)]
            return winners

    @classmethod
    async def get_participant_count(cls, interactive_id: int) -> int:
        async with new_session() as session:
            stmt = select(func.count()).where(
                QuizParticipant.interactive_id == interactive_id
            )
            result = await session.execute(stmt)
            return result.scalar_one()
