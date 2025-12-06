from typing import List

from sqlalchemy import select, delete, case
from database import new_session
from models import *

from datetime import datetime
import pytz

from interactivities.schemas import UserIdAndRole, InteractiveCreate, InteractiveId, \
    Interactive as InteractiveFull, Answer as AnswerFull, Question as QuestionFull, MyInteractives, FilterEnum, \
    InteractiveList
from minios3.schemas import ImageModel
import random
import string
import uuid
from urllib.parse import urlparse
import minios3.services as services


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
    async def create_interactive(cls, data: InteractiveCreate, images: list[ImageModel] | None) -> InteractiveId:
        async with new_session() as session:
            interactive_full_dict = data.model_dump()
            questions_list = interactive_full_dict.pop('questions')
            interactive_dict = interactive_full_dict

            new_interactive = Interactive(**interactive_dict)
            session.add(new_interactive)
            await session.flush()

            count_image = 0

            for question in questions_list:
                image = None
                if question["image"] == "image":
                    image_dict = images[count_image].model_dump()
                    image = Image(**image_dict)
                    session.add(image)
                    await session.flush()
                    image = image.id
                    count_image += 1
                elif question["image"] is not None and question["image"] != "":
                    path_parts = urlparse(question["image"]).path.strip('/').split('/')

                    bucket_name = path_parts[-2]
                    unique_filename = path_parts[-1]
                    result = await session.execute(
                        select(Image.id).where(Image.unique_filename == unique_filename,
                                               Image.bucket_name == bucket_name
                                               )
                    )
                    image = result.scalar_one_or_none()

                new_question = Question(
                    interactive_id=new_interactive.id,
                    text=question['text'],
                    position=question['position'],
                    score=question['score'],
                    type=question['type'],
                    image_id=image
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
    async def check_filename_exists(cls, unique_filename: str, bucket_name: str) -> bool:
        async with new_session() as session:
            result = await session.execute(
                select(Image.id).where(Image.unique_filename == unique_filename, Image.bucket_name == bucket_name)
            )
            exists = result.scalar_one_or_none() is not None
            return exists

    @classmethod
    async def generate_unique_filename(cls, ext: str, bucket_name: str) -> str:
        while True:
            unique_filename = f"{uuid.uuid4()}.{ext}"
            if not await cls.check_filename_exists(unique_filename=unique_filename, bucket_name=bucket_name):
                return unique_filename

    @classmethod
    async def get_user_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
            user_id = result.scalar_one_or_none()
            return user_id

    @classmethod
    async def get_interactives(cls, user_id: int, filter: FilterEnum, from_number: int,
                               to_number: int) -> MyInteractives:
        async with new_session() as session:
            # Подзапрос для подсчета количества участников
            participant_count_subq = (
                select(
                    QuizParticipant.interactive_id,
                    func.count(QuizParticipant.id).label('participant_count')
                )
                .group_by(QuizParticipant.interactive_id)
                .subquery()
            )

            # Вычисляем дату для сортировки и отображения
            date_field = case(
                (Interactive.conducted == True, Interactive.date_completed),
                else_=Interactive.created_at
            ).label("display_date")

            # Базовый запрос с общими полями
            base_query = (
                select(
                    Interactive.id,
                    Interactive.title,
                    Interactive.target_audience,
                    date_field,
                    Interactive.created_at,
                    Interactive.conducted,
                    Interactive.date_completed,
                    func.coalesce(participant_count_subq.c.participant_count, 0).label('participant_count')
                )
                .join(
                    participant_count_subq,
                    Interactive.id == participant_count_subq.c.interactive_id,
                    isouter=True
                )
                .where(Interactive.created_by_id == user_id)
            )

            # Применяем фильтры
            if filter == FilterEnum.conducted:
                base_query = base_query.where(Interactive.conducted == True)
            elif filter == FilterEnum.not_conducted:
                base_query = base_query.where(Interactive.conducted == False)
            # Для FilterEnum.all не добавляем дополнительных условий

            # Сортируем по вычисленной дате (date_completed для проведенных, created_at для остальных)
            base_query = base_query.order_by(date_field.desc())

            # Выполняем запрос для получения общего количества (для определения is_end)
            count_query = select(func.count()).select_from(base_query.alias())
            total_count_result = await session.execute(count_query)
            total_count = total_count_result.scalar()

            # Применяем пагинацию
            query_with_pagination = base_query.offset(from_number).limit(to_number - from_number + 1)

            # Выполняем основной запрос
            result = await session.execute(query_with_pagination)
            interactives_data = result.all()

            # Преобразуем данные в схему
            interactives_list = []
            for interactive in interactives_data:
                # Используем уже вычисленное поле display_date
                # date_str = interactive.display_date.strftime("%d.%m.%y %H:%M") if interactive.display_date else None

                if interactive.display_date.tzinfo is None:
                    # Сначала добавляем UTC, затем конвертируем
                    utc_time = pytz.UTC.localize(interactive.display_date)
                    yekat_time = utc_time.astimezone(pytz.timezone('Asia/Yekaterinburg'))
                    date_str = yekat_time.strftime("%d.%m.%y %H:%M")
                else:
                    # Если уже с часовым поясом, просто конвертируем
                    yekat_time = interactive.display_date.astimezone(pytz.timezone('Asia/Yekaterinburg'))
                    date_str = yekat_time.strftime("%d.%m.%y %H:%M")

                interactives_list.append(InteractiveList(
                    title=interactive.title,
                    target_audience=interactive.target_audience,
                    participant_count=interactive.participant_count,
                    is_conducted=interactive.conducted,
                    id=interactive.id,
                    date_completed=date_str
                ))

            # Определяем, достигнут ли конец списка
            is_end = total_count <= to_number + 1 or len(interactives_list) < (to_number - from_number + 1)

            return MyInteractives(
                interactives_list=interactives_list,
                is_end=is_end
            )

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
                image = ""
                if question.image_id is not None:
                    image_result = await session.execute(
                        select(Image)
                        .where(Image.id == question.image_id)
                    )
                    image_data = image_result.scalars().first()
                    if image_data is not None:
                        image = F"https://storage.yandexcloud.net/{image_data.bucket_name}/{image_data.unique_filename}"

                questions_data.append(
                    QuestionFull(
                        text=question.text,
                        position=question.position,
                        answers=answers_data,
                        type=question.type,
                        image=image,
                        score=question.score,
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
            data: InteractiveFull,
            images: list[ImageModel] | None
    ) -> InteractiveId:
        async with new_session() as session:
            # 1. Получаем интерактив
            interactive = await session.get(Interactive, interactive_id)
            if not interactive:
                raise ValueError(f"Интерактив с ID {interactive_id} не найден")

            # 2. Получаем все вопросы интерактива (до удаления)
            old_questions_result = await session.execute(
                select(Question.id, Question.image_id)
                .where(Question.interactive_id == interactive_id)
            )
            old_questions = old_questions_result.all()
            old_image_ids = {q.image_id for q in old_questions if q.image_id is not None}

            # 3. Удаляем все ответы
            await session.execute(
                delete(Answer)
                .where(Answer.question_id.in_(
                    select(Question.id)
                    .where(Question.interactive_id == interactive_id)
                ))
            )

            # 4. Удаляем все вопросы
            await session.execute(
                delete(Question)
                .where(Question.interactive_id == interactive_id)
            )

            # 5. Обновляем поля интерактива
            update_data = data.model_dump(exclude={"questions"})
            for key, value in update_data.items():
                setattr(interactive, key, value)

            # 6. Создаём новые вопросы и ответы
            count_image = 0
            new_image_ids = set()
            for question_data in data.questions:
                image_id = None

                # Если пришло новое изображение
                if question_data.image == "image":
                    image_dict = images[count_image].model_dump()
                    image = Image(**image_dict)
                    session.add(image)
                    await session.flush()
                    image_id = image.id
                    new_image_ids.add(image_id)
                    count_image += 1

                # Если пришёл путь к существующему изображению
                elif question_data.image:
                    path_parts = urlparse(question_data.image).path.strip('/').split('/')
                    bucket_name = path_parts[-2]
                    unique_filename = path_parts[-1]
                    result = await session.execute(
                        select(Image.id).where(Image.unique_filename == unique_filename,
                                               Image.bucket_name == bucket_name
                                               )
                    )
                    image_id = result.scalar_one_or_none()
                    if image_id:
                        new_image_ids.add(image_id)

                new_question = Question(
                    interactive_id=interactive_id,
                    text=question_data.text,
                    position=question_data.position,
                    score=question_data.score,
                    type=question_data.type,
                    image_id=image_id
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

            # 7. Проверяем, какие старые изображения больше не используются
            images_to_check = old_image_ids - new_image_ids
            if images_to_check:
                # Ищем, используются ли они где-то ещё
                used_images_result = await session.execute(
                    select(Question.image_id)
                    .where(Question.image_id.in_(images_to_check))
                )
                still_used = {row.image_id for row in used_images_result if row.image_id is not None}
                unused_image_ids = images_to_check - still_used

                # Удаляем неиспользуемые
                if unused_image_ids:
                    images_result = await session.execute(
                        select(Image).where(Image.id.in_(unused_image_ids))
                    )
                    unused_images: List[Image] = [row[0] for row in images_result]

                    for image in unused_images:
                        result_minion = await services.delete_image_from_minio(unique_filename=image.unique_filename,
                                                                               bucket_name=image.bucket_name)
                        if result_minion != "True":
                            print(f"⚠️ Ошибка при удалении {image.unique_filename} из S3: {result_minion}")

                    await session.execute(
                        delete(Image).where(Image.id.in_(unused_image_ids))
                    )

            await session.commit()
            return InteractiveId(interactive_id=interactive_id)

    @classmethod
    async def delite_interactive(
            cls,
            interactive_id: int,
    ) -> InteractiveId:
        async with new_session() as session:
            # 1. Проверяем, существует ли интерактив
            interactive = await session.get(Interactive, interactive_id)
            if not interactive:
                raise ValueError(f"Интерактив с ID {interactive_id} не найден")

            # 2. Получаем вопросы интерактива
            questions_result = await session.execute(
                select(Question.id, Question.image_id)
                .where(Question.interactive_id == interactive_id)
            )
            questions = questions_result.all()

            question_ids = [q.id for q in questions]
            image_ids = {q.image_id for q in questions if q.image_id is not None}

            # 3. Удаляем ответы
            if question_ids:
                await session.execute(
                    delete(Answer).where(Answer.question_id.in_(question_ids))
                )

            # 4. Удаляем вопросы
            await session.execute(
                delete(Question).where(Question.id.in_(question_ids))
            )

            # 5. Проверяем, какие изображения теперь можно удалить
            if image_ids:
                # Найдём изображения, больше нигде не используемые
                used_images_result = await session.execute(
                    select(Question.image_id)
                    .where(Question.image_id.in_(image_ids))
                )
                used_image_ids = {row.image_id for row in used_images_result if row.image_id is not None}
                unused_image_ids = image_ids - used_image_ids

                if unused_image_ids:
                    # Получаем данные об этих изображениях
                    images_result = await session.execute(
                        select(Image).where(Image.id.in_(unused_image_ids))
                    )
                    images_to_delete: List[Image] = [row[0] for row in images_result]

                    # Удаляем объекты из бакета MinIO
                    for image in images_to_delete:
                        result_minion = await services.delete_image_from_minio(unique_filename=image.unique_filename,
                                                                               bucket_name=image.bucket_name)
                        if result_minion != "True":
                            print(f"⚠️ Ошибка при удалении {image.unique_filename} из S3: {result_minion}")

                    # Удаляем записи из таблицы Image
                    await session.execute(
                        delete(Image).where(Image.id.in_(unused_image_ids))
                    )

            # 6. Удаляем сам интерактив
            await session.execute(
                delete(Interactive).where(Interactive.id == interactive_id)
            )

            await session.commit()

            return InteractiveId(interactive_id=interactive_id)

    @classmethod
    async def remove_participant_from_interactive(cls, interactive_id: int):
        async with new_session() as session:
            async with session.begin():
                # Находим всех участников интерактива
                participants_result = await session.execute(
                    select(QuizParticipant)
                    .where(QuizParticipant.interactive_id == interactive_id)
                )
                participants = participants_result.scalars().all()

                if not participants:
                    return

                # Собираем ID всех участников для удаления ответов
                participant_ids = [participant.id for participant in participants]

                # Удаляем все ответы участников этого интерактива
                await session.execute(
                    delete(UserAnswer)
                    .where(UserAnswer.participant_id.in_(participant_ids))
                )

                # Удаляем всех участников интерактива
                await session.execute(
                    delete(QuizParticipant)
                    .where(QuizParticipant.interactive_id == interactive_id)
                )

                await session.commit()
                return

    @classmethod
    async def get_interactive_title(cls, interactive_id: int, user_id: int) -> str | None:
        async with new_session() as session:
            result = await session.execute(
                select(Interactive.title)
                .where(Interactive.id == interactive_id,
                       Interactive.created_by_id == user_id,
                       Interactive.conducted == True)
            )
            row = result.one_or_none()
            if row is None:
                return None
            return row.title
