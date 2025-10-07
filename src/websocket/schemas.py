from pydantic import BaseModel, ConfigDict
import enum
from users.schemas import UserRoleEnum
from fastapi import WebSocket


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


class DataPause(BaseModel):
    state: StatePause
    timer_n: int


class Pause(BaseModel):
    pause: DataPause


class UserConnectWSInfo(BaseModel):
    telegram_id: int
    interactive_id: int
    role: UserRoleEnum


class InteractiveInfo(BaseModel):
    interactive_id: int
    code: str
    title: str
    description: str
    answer_duration: int
    discussion_duration: int
    countdown_duration: int


class DataStageWaiting(BaseModel):
    title: str
    description: str
    code: str
    participants_active: int


class StageWaiting(BaseModel):
    stage: Stage
    data: DataStageWaiting
    pause: DataPause


class DataStageCountdown(BaseModel):
    timer: int


class StageCountdown(BaseModel):
    stage: Stage
    data: DataStageCountdown


class Question(BaseModel):
    id: int
    text: str
    position: int


class Answer(BaseModel):
    id: int
    text: str


class AnswerGet(Answer):
    is_correct: bool


class DataStageQuestion(BaseModel):
    questions_count: int
    timer: int
    timer_duration: int
    title: str
    code: str
    question: Question
    answers: list[Answer]


class StageQuestion(BaseModel):
    stage: Stage
    data: DataStageQuestion
    pause: DataPause


class Percentage(BaseModel):
    id: int
    percentage: float


class DataStageDiscussion(BaseModel):
    questions_count: int
    timer: int
    timer_duration: int
    title: str
    code: str
    question: Question
    id_correct_answer: int
    percentages: list[Percentage]


class StageDiscussion(BaseModel):
    stage: Stage
    data: DataStageDiscussion
    pause: DataPause


class Winner(BaseModel):
    position: int
    username: str


class DataStageEnd(BaseModel):
    title: str
    participants_total: int
    winners: list[Winner]


class StageEnd(BaseModel):
    stage: Stage
    data: DataStageEnd


class LeaderSent(BaseModel):
    interactive_status: InteractiveStatus


class ParticipantSent(BaseModel):
    answer_id: int


class CreateQuizParticipant(BaseModel):
    user_id: int
    interactive_id: int


class PutUserAnswers(BaseModel):
    question_id: int
    participant_id: int
    answer_id: int


class WebSocketConnection(BaseModel):
    websocket: WebSocket
    user_id: int
    role: UserRoleEnum

    model_config = ConfigDict(arbitrary_types_allowed=True)
