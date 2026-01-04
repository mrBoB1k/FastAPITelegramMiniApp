from pydantic import BaseModel
from models import UserRoleEnum

class UserRole(BaseModel):
    role: UserRoleEnum

class UserRegister(BaseModel):
    telegram_id: int
    username: str | None = ""
    first_name: str
    last_name: str | None = None
    phone_number: str | None = None
