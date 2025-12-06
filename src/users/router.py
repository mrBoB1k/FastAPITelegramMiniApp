from fastapi import APIRouter, Depends, HTTPException, status

from users.schemas import UserRegister, TelegramId, UserRole, UsersChangeRole, UsersBase, UserRoleEnum
from typing import Annotated
from users.repository import Repository

from interactivities.repository import Repository as Repository_Interactivities

from websocket.router import manager as ws_manager

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
        if user.username is None:
            user.username = ""
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


@router.delete("/{telegram_id}")
async def delete_interactive(
        telegram_id: Annotated[TelegramId, Depends()],
):
    user_id_role = await Repository_Interactivities.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_id = user_id_role.user_id

    # удаление всех интерактивов вместе с ответами участников
    interactive_ids = await Repository.get_all_interactive_id(user_id)
    for interactive_id in interactive_ids:
        if interactive_id in ws_manager.interactive_sessions:
            await ws_manager.disconnect_delete(interactive_id=interactive_id)

        else:
            await Repository_Interactivities.remove_participant_from_interactive(interactive_id=interactive_id)

        new_interactive_id = await Repository_Interactivities.delite_interactive(interactive_id=interactive_id)
        if new_interactive_id.interactive_id != interactive_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"какая-то хуйня случилась с удалением интерактив {interactive_id}")

    # удаление всех участий в интерактивах
    quiz_participants_ids = await Repository.get_all_quiz_participants_id(user_id)
    for quiz_participant_id in quiz_participants_ids:
        flag = await Repository.delete_quiz_participant_and_answers(quiz_participant_id=quiz_participant_id)
        if not flag:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"какая-то хуйня случилась с удалением твоего участия в интерактиве с quiz_participant_id {quiz_participant_id}")

    # удаление пользователя
    flag = await Repository.delete_user(user_id=user_id)
    if not flag:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Ну какая-то хуйня пошла, и не смог удалить пользователя")

    return
