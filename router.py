from fastapi import APIRouter, Depends, HTTPException, status
from schemas import UserRegister, UserRoleEnum, TelegramId, UserRole
from typing import Annotated
from repository import Repository

router = APIRouter(
    prefix="/api/users",
    tags=["/api/users"]
)


@router.post("/register")
async def register(
        user: Annotated[UserRegister, Depends()],
) -> UserRole:
    user_role = await Repository.get_role_by_telegram_id(user.telegram_id)
    if user_role is None:
        user_role = await Repository.register_user(user)
    return {"role": user_role}


@router.get("/me/role")
async def get_me_role(
        data: Annotated[TelegramId, Depends()],
) -> UserRole:
    user_role = await Repository.get_role_by_telegram_id(data.telegram_id)
    if user_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"role": user_role}
