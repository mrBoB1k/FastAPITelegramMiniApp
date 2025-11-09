from datetime import datetime

from pydantic import BaseModel, field_validator, ValidationError
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
    username: str | None = ""
    first_name: str
    last_name: str | None = None
    phone_number: str | None = None

class UsersBase(BaseModel):
    id: int
    telegram_id: int
    username: str
    first_name: str
    last_name: str | None = None
    phone_number: str | None = None
    role: UserRoleEnum
    created_at: datetime | None = None

class UsersChangeRole(BaseModel):
    telegram_id: int
    role: UserRoleEnum