from fastapi import UploadFile
from pydantic import BaseModel, Field
import enum

from models import UserRoleEnum

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

class FilterEnum(str, enum.Enum):
    all = "all"
    conducted = "conducted"
    not_conducted = "not_conducted"


class TelegramId(BaseModel):
    telegram_id: int

class GetDataInteractive(BaseModel):
    telegram_id: int
    filter: FilterEnum
    from_number: int
    to_number: int

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
                "answer_duration": 5,
                "discussion_duration": 5,
                "countdown_duration": 5,
                "questions": [
                    {
                        "text": "Что делает функция len()?",
                        "position": 1,
                        "type": "one",
                        "image": "",
                        "score": 1,
                        "answers": [
                            {"text": "Возвращает длину объекта", "is_correct": True},
                            {"text": "Создает новый список", "is_correct": False}
                        ]
                    }
                ]
            }
        }


class InteractiveId(BaseModel):
    interactive_id: int


class InteractiveCode(BaseModel):
    code: str


class InteractiveCreate(Interactive):
    code: str
    created_by_id: int
    conducted: bool = False

class InteractiveList(BaseModel):
    title: str
    target_audience: str | None = None
    participant_count: int
    is_conducted: bool
    id: int
    date_completed: str | None = None
    username: str
    is_you: bool


class MyInteractives(BaseModel):
    interactives_list: list[InteractiveList]
    is_end: bool
