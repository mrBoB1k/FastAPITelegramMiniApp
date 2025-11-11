from pydantic import BaseModel, ConfigDict, field_validator, ValidationError
import enum
from users.schemas import UserRoleEnum
from fastapi import WebSocket
from interactivities.schemas import InteractiveType as QuestionType


# enum для обработки логики
class Stage(str, enum.Enum):
    waiting = "waiting"
    countdown = "countdown"
    question = "question"
    discussion = "discussion"
    end = "end"


class InteractiveStatus(str, enum.Enum):
    pause = "pause"
    going = "going"
    end = "end"
    more_pause = "more_pause"


class StatePause(str, enum.Enum):
    no = "no"
    yes = "yes"
    timer_n = "timer_n"


# обработка паузы
class DataPause(BaseModel):
    state: StatePause
    timer_n: int


# для ссоздания InteractiveSession
class InteractiveInfo(BaseModel):
    interactive_id: int
    code: str
    title: str
    description: str
    answer_duration: int
    discussion_duration: int
    countdown_duration: int


# для отправки нужных json по websocket
class DataStageWaiting(BaseModel):
    title: str
    description: str
    code: str
    participants_active: int


class StageWaiting(BaseModel):
    stage: Stage
    data: DataStageWaiting
    pause: DataPause


###############################################################
class DataStageCountdown(BaseModel):
    timer: int


class StageCountdown(BaseModel):
    stage: Stage
    data: DataStageCountdown


###############################################################
class Answer(BaseModel):
    id: int
    text: str


class AnswerGet(Answer):
    is_correct: bool


class Question(BaseModel):
    id: int
    text: str
    position: int
    question_weight: int
    type: QuestionType
    image: str | None = None


class DataStageQuestion(BaseModel):
    questions_count: int
    timer: int
    timer_duration: int
    title: str
    code: str
    question: Question


class StageQuestion(BaseModel):
    stage: Stage
    pause: DataPause
    data: DataStageQuestion
    data_answers: list[Answer] | None = None


###############################################################
class PercentageTypeText(BaseModel):
    id: int
    text: str
    percentage: float

class Percentage(BaseModel):
    id: int
    percentage: float


class DataAnswersStageDiscussionTypeOne(BaseModel):
    id_correct_answer: int
    percentages: list[Percentage]


class DataAnswersStageDiscussionTypeMany(BaseModel):
    id_correct_answer: list[int]
    percentages: list[Percentage]


class CorrectAnswerStageDiscussionTypeTextLeader(BaseModel):
    text: str
    percentage: float


class DataAnswersStageDiscussionTypeTextLeader(BaseModel):
    correct_answers: list[CorrectAnswerStageDiscussionTypeTextLeader]


class DataAnswersStageDiscussionTypeTextParticipantTrue(BaseModel):
    is_correct: bool
    answer: str
    percentage: float


class DataAnswersStageDiscussionTypeTextParticipantFalse(BaseModel):
    is_correct: bool
    answers: list[CorrectAnswerStageDiscussionTypeTextLeader]


class DataStageDiscussion(BaseModel):
    questions_count: int
    timer: int
    timer_duration: int
    title: str
    code: str
    question: Question


class WinnerDiscussion(BaseModel):
    position: int
    username: str
    score: int


class StageDiscussion(BaseModel):
    stage: Stage
    pause: DataPause
    data: DataStageDiscussion
    data_answers: DataAnswersStageDiscussionTypeOne | DataAnswersStageDiscussionTypeMany | DataAnswersStageDiscussionTypeTextLeader | DataAnswersStageDiscussionTypeTextParticipantTrue | DataAnswersStageDiscussionTypeTextParticipantFalse | None
    winners: list[WinnerDiscussion]


class StageDiscussionParticipant(StageDiscussion):
    score: int


###############################################################
class Winner(WinnerDiscussion):
    time: int

class ScoreStageEnd(BaseModel):
    position: int
    score: int
    time: int


class DataStageEnd(BaseModel):
    title: str
    participants_total: int
    winners: list[Winner] | None = None


class StageEnd(BaseModel):
    stage: Stage
    data: DataStageEnd


class StageEndParticipant(StageEnd):
    score: ScoreStageEnd


# обработка сообщений отправленных на бек по websocket
class LeaderSent(BaseModel):
    interactive_status: InteractiveStatus


class ParticipantSent(BaseModel):
    answer_id: int | None = None
    answer_ids: list[int] | None = None
    answer_text: str | None = None


# добавление в бд участника интерактива
class CreateQuizParticipant(BaseModel):
    user_id: int
    interactive_id: int
    total_time: int


# облегчение взаимодействия
class WebSocketConnection(BaseModel):
    websocket: WebSocket
    user_id: int
    role: UserRoleEnum

    model_config = ConfigDict(arbitrary_types_allowed=True)
