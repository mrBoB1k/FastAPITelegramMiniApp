from sqlalchemy import select, exists, delete, desc, asc
from database import new_session
from models import *
from websocket.schemas import InteractiveInfo, Question as QuestionSchema, CreateQuizParticipant, QuestionType, \
    Percentage, Winner, AnswerGet, WinnerDiscussion, PercentageTypeText
from collections import Counter


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
                select(Question, Image)
                .outerjoin(Image, Question.image_id == Image.id)
                .where(Question.interactive_id == interactive_id)
                .order_by(Question.position)
            )

            questions_with_images = result.all()
            return [
                QuestionSchema(
                    id=q.id,
                    text=q.text,
                    position=q.position,
                    question_weight=q.score,
                    type=q.type,
                    image=f"https://carclicker.ru/{img.bucket_name}/{img.unique_filename}" if img else None
                )
                for q, img in questions_with_images
            ]

    @classmethod
    async def get_question_answers(cls, question_id: int) -> list[AnswerGet]:
        async with new_session() as session:
            result = await session.execute(
                select(Answer)
                .where(Answer.question_id == question_id)
            )

            answers = result.scalars().all()
            return [
                AnswerGet(id=a.id, text=a.text, is_correct=a.is_correct)
                for a in answers
            ]

    @classmethod
    async def register_quiz_participant(cls, data: CreateQuizParticipant) -> int:
        async with new_session() as session:
            flag = await session.execute(
                select(QuizParticipant)
                .where(QuizParticipant.interactive_id == data.interactive_id, QuizParticipant.user_id == data.user_id)
            )

            flag = flag.scalar_one_or_none()
            if flag is None:
                participant_dict = data.model_dump()

                participant = QuizParticipant(**participant_dict)
                session.add(participant)

                await session.flush()
                await session.commit()
                return participant.id
            else:
                return flag.id

    @classmethod
    async def check_register_quiz_participant(cls, data: CreateQuizParticipant) -> bool:
        async with new_session() as session:
            flag = await session.execute(
                select(QuizParticipant)
                .where(QuizParticipant.interactive_id == data.interactive_id, QuizParticipant.user_id == data.user_id)
            )

            flag = flag.scalar_one_or_none()
            return flag is not None

    @classmethod
    async def put_user_answers(cls, participant_id: int, question_id: int, time: int, is_correct: bool,
                               question_type: QuestionType, answer_id: int = None, answer_ids: list[int] = None,
                               answer_text: str = None, matched_answer_id: int = None) -> None:
        async with new_session() as session:
            flag_answer = await session.execute(
                select(UserAnswer)
                .where(UserAnswer.participant_id == participant_id, UserAnswer.question_id == question_id)
            )
            flag_answer = flag_answer.scalar_one_or_none()
            if flag_answer is None:
                user_answer = UserAnswer(
                    participant_id=participant_id,
                    question_id=question_id,
                    time=time,
                    is_correct=is_correct
                )
                if question_type == QuestionType.one:
                    user_answer.set_single_choice(answer_id)
                elif question_type == QuestionType.many:
                    user_answer.set_multiple_choice(answer_ids)
                elif question_type == QuestionType.text:
                    user_answer.set_text_answer(answer_text, matched_answer_id=matched_answer_id)
                session.add(user_answer)
                await session.flush()
                await session.commit()
            else:
                if question_type == QuestionType.one:
                    flag_answer.set_single_choice(answer_id)
                elif question_type == QuestionType.many:
                    flag_answer.set_multiple_choice(answer_ids)
                elif question_type == QuestionType.text:
                    flag_answer.set_text_answer(answer_text, matched_answer_id=matched_answer_id)
                flag_answer.time = time
                flag_answer.is_correct = is_correct
                await session.commit()
                await session.refresh(flag_answer)

    @classmethod
    async def get_percentages(cls, question_id: int) -> list[Percentage]:
        async with new_session() as session:
            # Получаем все ответы на вопрос
            answers = (await session.execute(
                select(Answer).where(Answer.question_id == question_id)
            )).scalars().all()

            # Получаем все user_answers для этого вопроса
            user_answers = (await session.execute(
                select(UserAnswer).where(UserAnswer.question_id == question_id)
            )).scalars().all()

            # Фильтруем только one/many типы
            filtered_user_answers = [
                ua for ua in user_answers
                if ua.answer_type in ("one", "many")
            ]

            # Подсчёт выборов
            total = len(filtered_user_answers)
            answer_counts = {a.id: 0 for a in answers}

            for ua in filtered_user_answers:
                for ans_id in ua.selected_answer_ids:
                    if ans_id in answer_counts:
                        answer_counts[ans_id] += 1

            # Конвертация в проценты
            result = []
            if total > 0:
                for ans_id, count in answer_counts.items():
                    percentage = round((count / total) * 100, 2)
                    result.append(Percentage(id=ans_id, percentage=percentage))
            else:
                for ans_id in answer_counts:
                    result.append(Percentage(id=ans_id, percentage=0.0))

            return result

    @classmethod
    async def get_percentages_for_text(cls, question_id: int) -> list[PercentageTypeText]:
        async with new_session() as session:
            # Получаем все ответы
            answers = (await session.execute(
                select(Answer).where(Answer.question_id == question_id)
            )).scalars().all()

            # Получаем все текстовые ответы пользователей
            user_answers = (await session.execute(
                select(UserAnswer).where(UserAnswer.question_id == question_id)
            )).scalars().all()

            text_user_answers = [ua for ua in user_answers if ua.answer_type == "text"]
            total = len(text_user_answers)

            # читаем совпадения по matched_answer_id
            answer_counts = {a.id: 0 for a in answers}
            for ua in text_user_answers:
                for ans_id in ua.selected_answer_ids:
                    if ans_id in answer_counts:
                        answer_counts[ans_id] += 1

            # Формируем итог
            result = []
            if total > 0:
                for ans in answers:
                    count = answer_counts.get(ans.id, 0)
                    percentage = round((count / total) * 100, 2)
                    result.append(
                        PercentageTypeText(
                            id=ans.id,
                            text=ans.text,
                            percentage=percentage
                        )
                    )
            else:
                for ans in answers:
                    result.append(
                        PercentageTypeText(
                            id=ans.id,
                            text=ans.text,
                            percentage=0.0
                        )
                    )

            return result

    @classmethod
    async def get_user_score(cls, user_id: int, interactive_id:int) -> int:
        async with new_session() as session:
            stmt = (
                select(func.coalesce(func.sum(Question.score), 0))
                .join(UserAnswer, UserAnswer.question_id == Question.id)
                .join(QuizParticipant, QuizParticipant.id == UserAnswer.participant_id)
                .where(
                    QuizParticipant.user_id == user_id,
                    QuizParticipant.interactive_id == interactive_id,
                    UserAnswer.is_correct == True
                )
            )

            result = await session.scalar(stmt)
            return int(result or 0)

    @classmethod
    async def is_user_answer_correct(cls, user_id: int, question_id: int) -> bool:
        async with new_session() as session:
            stmt = (
                select(UserAnswer.is_correct)
                .join(QuizParticipant, QuizParticipant.id == UserAnswer.participant_id)
                .where(
                    QuizParticipant.user_id == user_id,
                    UserAnswer.question_id == question_id
                )
                .limit(1)
            )

            result = await session.scalar(stmt)
            return bool(result) if result is not None else False

    @classmethod
    async def get_user_matched_answer_id(cls, user_id: int, question_id: int) -> int | None:
        async with new_session() as session:
            query = (
                select(UserAnswer)
                .join(QuizParticipant, QuizParticipant.id == UserAnswer.participant_id)
                .where(
                    QuizParticipant.user_id == user_id,
                    UserAnswer.question_id == question_id
                )
            )

            result = await session.execute(query)
            user_answer = result.scalars().first()


            if user_answer and user_answer.answer_type == "text":
                data = user_answer.selected_answer_ids
                if data is not None:
                    if len(data) > 0:
                        return data[0]
            return None

    @classmethod
    async def get_id_correct_answers(cls, question_id: int) -> list[int]:
        async with new_session() as session:
            result = await session.execute(
                select(Answer.id)
                .where(
                    Answer.question_id == question_id,
                    Answer.is_correct == True
                )
            )
            rows = result.scalars().all()
            return rows or []

    @classmethod
    async def mark_interactive_conducted(cls, interactive_id: int):
        async with new_session() as session:
            interactive = await session.get(Interactive, interactive_id)
            if interactive:
                interactive.conducted = True
                interactive.date_completed = func.now()
                await session.commit()

    @classmethod
    async def get_winners_discussion(cls, interactive_id: int) -> list[WinnerDiscussion]:
        async with new_session() as session:
            # 1. Получаем всех участников викторины с их результатами за один запрос
            stmt = (
                select(
                    QuizParticipant.id,
                    QuizParticipant.user_id,
                    QuizParticipant.total_time,
                    User.username,
                    func.coalesce(func.sum(Question.score), 0).label('total_score')
                )
                .select_from(QuizParticipant)
                .join(User, User.id == QuizParticipant.user_id)
                .outerjoin(
                    UserAnswer,
                    (UserAnswer.participant_id == QuizParticipant.id) &
                    (UserAnswer.is_correct == True)
                )
                .outerjoin(Question, Question.id == UserAnswer.question_id)
                .where(QuizParticipant.interactive_id == interactive_id)
                .group_by(
                    QuizParticipant.id,
                    QuizParticipant.user_id,
                    QuizParticipant.total_time,
                    User.username
                )
            )

            result = await session.execute(stmt)
            participants_data = result.all()

            if not participants_data:
                return []

            # 2. Формируем список участников
            participants_list = [
                {
                    "user_id": user_id,
                    "username": username,
                    "score": int(total_score),
                    "total_time": total_time
                }
                for participant_id, user_id, total_time, username, total_score in participants_data
            ]

            # 3. Сортировка по score DESC, total_time ASC
            participants_list.sort(key=lambda x: (-x["score"], x["total_time"]))
            winners_list = participants_list[:3]

            # 4. Формируем список победителей
            winners = [
                WinnerDiscussion(
                    position=i + 1,
                    username=w["username"],
                    score=w["score"]
                )
                for i, w in enumerate(winners_list)
            ]

            return winners

    @classmethod
    async def get_winners(cls, interactive_id: int) -> list[Winner]:
        async with new_session() as session:
            # 1. Получаем всех участников викторины с их результатами за один запрос
            stmt = (
                select(
                    QuizParticipant.id,
                    QuizParticipant.user_id,
                    QuizParticipant.total_time,
                    User.username,
                    func.coalesce(func.sum(Question.score), 0).label('total_score')
                )
                .select_from(QuizParticipant)
                .join(User, User.id == QuizParticipant.user_id)
                .outerjoin(
                    UserAnswer,
                    (UserAnswer.participant_id == QuizParticipant.id) &
                    (UserAnswer.is_correct == True)
                )
                .outerjoin(Question, Question.id == UserAnswer.question_id)
                .where(QuizParticipant.interactive_id == interactive_id)
                .group_by(
                    QuizParticipant.id,
                    QuizParticipant.user_id,
                    QuizParticipant.total_time,
                    User.username
                )
            )

            result = await session.execute(stmt)
            participants_data = result.all()

            if not participants_data:
                return []

            # 2. Формируем список участников
            participants_list = [
                {
                    "user_id": user_id,
                    "username": username,
                    "score": int(total_score),
                    "total_time": total_time
                }
                for participant_id, user_id, total_time, username, total_score in participants_data
            ]

            # 3. Сортировка по score DESC, total_time ASC
            participants_list.sort(key=lambda x: (-x["score"], x["total_time"]))
            winners_list = participants_list[:3]

            # 4. Формируем список победителей
            winners = [
                Winner(
                    position=i + 1,
                    username=w["username"],
                    score=w["score"],
                    time=w["total_time"]
                )
                for i, w in enumerate(winners_list)
            ]

            return winners

    @classmethod
    async def get_participant_count(cls, interactive_id: int) -> int:
        async with new_session() as session:
            result = await session.execute(
                select(func.count().label('correct_count'))
                .where(QuizParticipant.interactive_id == interactive_id)
            )
            count = result.scalar()
            return count

    @classmethod
    async def remove_participant_from_interactive(cls, user_id: int, interactive_id: int):
        async with new_session() as session:
            async with session.begin():
                # Находим участника интерактива
                participant_result = await session.execute(
                    select(QuizParticipant)
                    .where(QuizParticipant.user_id == user_id,
                           QuizParticipant.interactive_id == interactive_id
                           )
                )
                participant = participant_result.scalar_one_or_none()

                if not participant:
                    return

                # Удаляем все ответы участника
                await session.execute(delete(UserAnswer)
                                      .where(UserAnswer.participant_id == participant.id)
                                      )

                # Удаляем участника
                await session.execute(
                    delete(QuizParticipant)
                    .where(QuizParticipant.id == participant.id)
                )

                await session.commit()
                return
