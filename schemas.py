from pydantic import BaseModel
from typing import Optional
import enum


class UserRoleEnum(str, enum.Enum):
    leader = "leader"
    participant = "participant"

class UserRole(BaseModel):
    role: UserRoleEnum

class TelegramId(BaseModel):
    telegram_id: int


class UserRegister(BaseModel):
    telegram_id: int
    username: str
    first_name: str
    last_name: str | None = None
    phone_number: str | None = None
