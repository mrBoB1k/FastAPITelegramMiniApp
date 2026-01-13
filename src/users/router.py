from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from models import UserRoleEnum

from users.repository import Repository
from users.schemas import UserRegister, UserRole

from organizations.repository import Repository as Repository_organization
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
        role = await Repository_organization.get_role_on_organizations_by_user_id(user_id)
        return UserRole(role=role.role)

    if user.username is None:
        user.username = ""

    user_data = await Repository.register_user(user)
    return UserRole(role=UserRoleEnum.participant)
