from sqlalchemy import select
from database import new_session
from models import *
from datetime import datetime
from interactivities.schemas import UserIdAndRole, InteractiveCreate, InteractiveId
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
