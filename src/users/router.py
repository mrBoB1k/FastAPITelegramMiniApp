from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from models import UserRoleEnum

from users.repository import Repository
from users.schemas import UserRegister, UserRole

router = APIRouter(
    prefix="/api/users",
    tags=["/api/users"]
)

@router.post("/register")
async def register(
        user: Annotated[UserRegister, Depends()],
) -> UserRole:
    user_id = await Repository.get_user_id_by_telegram_id(user.telegram_id)
    if user_id is not None:
        raise HTTPException(status_code=400, detail="User already registered")

    if user.username is None:
        user.username = ""

    user_data = await Repository.register_user(user)
    return UserRole(role=UserRoleEnum.participant)
