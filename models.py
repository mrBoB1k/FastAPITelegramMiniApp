from sqlalchemy import (
    Column, Integer, BigInteger, Text, Boolean, ForeignKey, TIMESTAMP, func
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base, relationship
import enum
from sqlalchemy import Enum


class UserRole(str, enum.Enum):
    leader = "leader"
    participant = "participant"


Base = declarative_base()


class User(AsyncAttrs, Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(Text, nullable=False)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=True)
    phone_number = Column(Text, nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class Interactive(AsyncAttrs, Base):
    __tablename__ = 'interactives'

    id = Column(Integer, primary_key=True)
    code = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    target_audience = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    responsible_full_name = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"))
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


class UserAnswer(AsyncAttrs, Base):
    __tablename__ = 'user_answers'

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey("quiz_participants.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    answer_id = Column(Integer, ForeignKey("answers.id"))
    answered_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class RoleChange(AsyncAttrs, Base):
    __tablename__ = 'role_changes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    changed_by_id = Column(Integer, ForeignKey("users.id"))
    old_role = Column(Text, nullable=False)
    new_role = Column(Text, nullable=False)
    changed_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
