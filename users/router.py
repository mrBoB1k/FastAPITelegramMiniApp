from fastapi import APIRouter, Depends, HTTPException, status
from users.schemas import UserRegister, TelegramId, UserRole, UsersChangeRole, UsersBase
from typing import Annotated
from users.repository import Repository

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
    return UserRole(role=user_role)


@router.get("/me/role")
async def get_me_role(
        data: Annotated[TelegramId, Depends()],
) -> UserRole:
    user_role = await Repository.get_role_by_telegram_id(data.telegram_id)
    if user_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRole(role=user_role)


@router.patch("/user_change_role")
async def change_role(
        data: Annotated[UsersChangeRole, Depends()],
) -> UsersBase:
    user_role = await Repository.get_role_by_telegram_id(data.telegram_id)
    if user_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_role == data.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User already has role")

    user = await Repository.change_role(data)
    return user
