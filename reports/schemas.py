from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import enum
from users.schemas import UserRoleEnum

class ExportEnum(str, enum.Enum):
    forLeader = "forLeader"
    forAnalise = "forAnalise"

class TelegramId(BaseModel):
    telegram_id: int

class PreviewInteractive(BaseModel):
    title: str
    participant_count: int
    target_audience: str
    location: str
    date_completed: str
    interactive_id: int

class InteractiveList(BaseModel):
    interactives_list: list[PreviewInteractive]

class InteractiveId(BaseModel):
    id: int

class ExportGet(BaseModel):
    telegram_id: int
    interactive_id: list[InteractiveId]
    report_type: ExportEnum

class ExportForAnalise(BaseModel):
    interactive_id: int #получает на входе
    title: str # из таблицы Interactive
    date_completed: str # из таблицы Interactive
    participant_count: int # посчитать кол-во записей в QuizParticipant у которых interactive_id = заданному
    question_count: int # посчитать кол-во записей в Question у которых interactive_id = заданному
    target_audience: str | None # из таблицы Interactive
    location: str | None # из таблицы Interactive
    responsible_full_name: str | None # из таблицы Interactive
    telegram_id: int # Надо найти в начале в QuizParticipant запись, которая относиться к заданному интерактиву и узнать из таблицы User telegram_id
    username: str # Надо найти в начале в QuizParticipant запись, которая относиться к заданному интерактиву и узнать из таблицы User username
    full_name: str # Надо найти в начале в QuizParticipant запись, которая относиться к заданному интерактиву и узнать из таблицы User first_name и last_name. После этого объединить их
    correct_answers_count: int # Надо найти в начале в QuizParticipant запись, которая относиться к заданному интерактиву. После в таблице UserAnswer посчитать кол-во, у которых answer_id в таблице Answer is_correct = true


class AnswerForLeaderHeader(BaseModel):
    id: int
    text: str
    is_correct: bool

class QuestionForLeaderHeader(BaseModel):
    id: int
    position: int
    text: str
    answers: list[AnswerForLeaderHeader]


class ExportForLeaderHeader(BaseModel):
    title: str
    interactive_id: int
    date_completed: str
    participant_count: int
    target_audience: str | None
    location: str | None
    responsible_full_name: str | None
    question: list[QuestionForLeaderHeader]

class ParticipantAnswer(BaseModel):
    question_id: int
    answer_id: int  # ID выбранного ответа

class ExportForLeaderBody(BaseModel):
    telegram_id: int
    username: str
    full_name: str
    correct_answers_count: int
    answers: list[ParticipantAnswer]

class ExportForLeaderData(BaseModel):
    header: ExportForLeaderHeader
    body: list[ExportForLeaderBody]  # Список участников с их ответами