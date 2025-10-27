from pydantic import BaseModel
from users.schemas import UserRoleEnum
from fastapi import UploadFile

import enum

class MinioData(BaseModel):
    file: bytes
    filename: str
    unique_filename: str
    content_type: str
    size: int

class InteractiveType(str, enum.Enum):
    one = "one"
    many = "many"
    text = "text"


class TelegramId(BaseModel):
    telegram_id: int


class UserIdAndRole(BaseModel):
    user_id: int
    role: UserRoleEnum


class Answer(BaseModel):
    text: str
    is_correct: bool


class Question(BaseModel):
    text: str
    position: int
    type: InteractiveType
    image: str
    score: int
    answers: list[Answer]


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

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Quiz about Python",
                "description": "Интерактивная викторина о языке Python",
                "target_audience": "Студенты",
                "location": "Онлайн",
                "responsible_full_name": "Иван Иванов",
                "answer_duration": 30,
                "discussion_duration": 15,
                "countdown_duration": 5,
                "questions": [
                    {
                        "text": "Что делает функция len()?",
                        "position": 1,
                        "type": "one",
                        "image": "",
                        "score": 10,
                        "answers": [
                            {"text": "Возвращает длину объекта", "is_correct": True},
                            {"text": "Создает новый список", "is_correct": False}
                        ]
                    }
                ]
            }
        }

class ReceiveInteractive(BaseModel):
    telegram_id: int
    interactive: Interactive


class InteractiveId(BaseModel):
    interactive_id: int


class InteractiveCode(BaseModel):
    code: str


class InteractiveCreate(Interactive):
    code: str
    created_by_id: int
    conducted: bool = False


class QuestionCreate(BaseModel):
    text: str
    position: int
    interactive_id: int


class InteractiveConducted(BaseModel):
    title: str
    question_count: int
    target_audience: str | None = None
    id: int
    date_completed: str | None = None


class MyInteractives(BaseModel):
    interactives_list_conducted: list[InteractiveConducted]
    interactives_list_not_conducted: list[InteractiveConducted]
