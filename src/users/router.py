from fastapi import APIRouter, Depends
from typing import Annotated

from dependencies import verify_key
from models import UserRoleEnum

from users.repository import Repository
from users.schemas import UserRegister, UserRole

router = APIRouter(
    prefix="/api/users",
    tags=["/api/users"]
)


@router.post("/register", dependencies=[Depends(verify_key)])
async def register(
        user: Annotated[UserRegister, Depends()],
) -> UserRole:
    user_id = await Repository.get_user_id_by_telegram_id(telegram_id=user.telegram_id)
    if user_id is not None:
        return UserRole(role=UserRoleEnum.participant)

    if user.username is None:
        user.username = ""

    user_data = await Repository.register_user(data=user)
    return UserRole(role=UserRoleEnum.participant)
