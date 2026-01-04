from sqlalchemy import (
    Column, Integer, BigInteger, Text, Boolean, ForeignKey, TIMESTAMP, func, JSON
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base, relationship
import enum
from sqlalchemy import Enum


class UserRoleEnum(str, enum.Enum):
    leader = "leader"
    participant = "participant"
    admin = "admin"
    organizer = "organizer"
    remote = "remote"


Base = declarative_base()


class User(AsyncAttrs, Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(Text, nullable=False)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=True)
    phone_number = Column(Text, nullable=True)
    # role = Column(Enum(UserRole), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class Organization(AsyncAttrs, Base):
    __tablename__ = 'organizations'

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False)


class OrganizationParticipant(AsyncAttrs, Base):
    __tablename__ = 'organization_participants'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(Text, nullable=False)
    role = Column(Enum(UserRoleEnum), nullable=False)


class Interactive(AsyncAttrs, Base):
    __tablename__ = 'interactives'

    id = Column(Integer, primary_key=True)
    code = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    target_audience = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    # responsible_full_name = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("organization_participants.id"))
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    answer_duration = Column(Integer, nullable=False)
    discussion_duration = Column(Integer, nullable=False)
    countdown_duration = Column(Integer, nullable=False)
    conducted = Column(Boolean, nullable=False)
    date_completed = Column(TIMESTAMP, nullable=True)


class Question(AsyncAttrs, Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True)
    interactive_id = Column(Integer, ForeignKey("interactives.id"))
    text = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    type = Column(Text, nullable=False)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=True)


class Image(AsyncAttrs, Base):
    __tablename__ = 'images'

    id = Column(Integer, primary_key=True)
    filename = Column(Text, nullable=False)
    unique_filename = Column(Text, nullable=False, unique=True)
    content_type = Column(Text, nullable=False)
    size = Column(BigInteger, nullable=False)
    bucket_name = Column(Text, nullable=False)


class Answer(AsyncAttrs, Base):
    __tablename__ = 'answers'

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)


class QuizParticipant(AsyncAttrs, Base):
    __tablename__ = 'quiz_participants'

    id = Column(Integer, primary_key=True)
    interactive_id = Column(Integer, ForeignKey("interactives.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    joined_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    total_time = Column(Integer, nullable=False)


class UserAnswer(AsyncAttrs, Base):
    __tablename__ = 'user_answers'

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey("quiz_participants.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    answer_data = Column(JSON, nullable=False)
    answered_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    time = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False)

    @property
    def answer_type(self):
        return self.answer_data.get('type')

    @property
    def selected_answer_ids(self):
        """Универсальный метод получения ID ответов"""
        if self.answer_type == 'one':
            return [self.answer_data.get('answer_id')]
        elif self.answer_type == 'many':
            return self.answer_data.get('answer_ids', [])
        elif self.answer_type == 'text':
            matched_id = self.answer_data.get('matched_answer_id')
            return [matched_id] if matched_id else []
        return []

    @property
    def text_answer(self):
        """Для текстовых ответов"""
        return self.answer_data.get('answer_text') if self.answer_type == 'text' else None

    def set_single_choice(self, answer_id):
        self.answer_data = {
            "type": "one",
            "answer_id": answer_id
        }

    def set_multiple_choice(self, answer_ids):
        self.answer_data = {
            "type": "many",
            "answer_ids": answer_ids
        }

    def set_text_answer(self, answer_text, matched_answer_id=None):
        self.answer_data = {
            "type": "text",
            "answer_text": answer_text,
            "matched_answer_id": matched_answer_id
        }
