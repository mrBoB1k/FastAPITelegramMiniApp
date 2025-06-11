from datetime import datetime

from pydantic import BaseModel
from typing import Optional
import enum

class InteractiveId(BaseModel):
    id: int

class SendGet(BaseModel):
    telegram_id: int
    interactive_id: list[InteractiveId]
    text: str

class TelegramId(BaseModel):
    telegram_id: int
