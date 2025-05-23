from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from interactivities.schemas import ReceiveInteractive, InteractiveId, InteractiveCreate, MyInteractives, TelegramId
from interactivities.repository import Repository
from users.schemas import UserRoleEnum
from datetime import datetime

router = APIRouter(
    prefix="/api/interactivities",
    tags=["/api/interactivities"]
)

@router.post("/")
async def creat_interactive(
        interactivitie: Annotated[ReceiveInteractive, Depends()],
) -> InteractiveId:
    user_id_role = await Repository.get_user_id_and_role_by_telegram_id(interactivitie.telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id_role.role != UserRoleEnum.leader:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can create interactives")

    user_id = user_id_role.user_id
    interactive = interactivitie.interactive

    for i, question in enumerate(interactive.questions):
        if question.position != i + 1:
            raise HTTPException(status_code=400, detail=f"Question positions must be sequential starting from 1")
        if len(question.answers) > 4:
            raise HTTPException(status_code=400, detail=f"Too many answers for question {question.text}")
        correct_answers = [a for a in question.answers if a.is_answered]
        if len(correct_answers) != 1:
            raise HTTPException(status_code=400,
                                detail=f"There must be exactly one correct answer in question {question.text}")

    code = await Repository.generate_unique_code()

    interactive_id = await Repository.create_interactive(
        InteractiveCreate(
            **interactive.model_dump(),
            code = code,
            created_by_id = user_id
        )
    )
    return interactive_id


@router.get("/me")
async def get_me(
    telegram_id: Annotated[TelegramId, Depends()],
) -> MyInteractives:
    user_id = await Repository.get_user_id(telegram_id.telegram_id)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    interactives_list_conducted = await Repository.get_interactives(user_id, conducted=True)
    interactives_list_not_conducted = await Repository.get_interactives(user_id, conducted=False)

    return MyInteractives(interactives_list_conducted = interactives_list_conducted, interactives_list_not_conducted= interactives_list_not_conducted)