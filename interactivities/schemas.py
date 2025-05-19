from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import enum
from users.schemas import UserRoleEnum


class UserIdAndRole(BaseModel):
    user_id: int
    role: UserRoleEnum


class Answer(BaseModel):
    text: str
    is_answered: bool
# question_id


class Question(BaseModel):
    text: str
    position: int
    answers: list[Answer]
# interactive_id


class Interactive(BaseModel):
    title: str
    description: str
    target_audience: str | None = None
    location: str | None = None
    responsible_full_name: str | None = None
    answer_duration: int
    discussion_duration: int
    countdown_duration: int
    questions: list[Question]
# code created_by_id created_at conducted


class ReceiveInteractive(BaseModel):
    telegram_id: int
    interactive: Interactive


class InteractiveId(BaseModel):
    interactive_id: int


class InteractiveCreate(Interactive):
    code: str
    created_by_id: int
    conducted: bool = False

class QuestionCreate(BaseModel):
    text: str
    position: int
    interactive_id: int