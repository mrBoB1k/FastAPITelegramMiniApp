from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
from typing import Annotated
from interactivities.schemas import ReceiveInteractive, InteractiveId, InteractiveCreate, MyInteractives, TelegramId, \
    InteractiveCode, Interactive
from interactivities.repository import Repository
from users.schemas import UserRoleEnum
from websocket.router import manager as ws_router
from websocket.InteractiveSession import Stage

router = APIRouter(
    prefix="/api/interactivities",
    tags=["/api/interactivities"]
)

@router.post("/")
async def creat_interactive(
        interactivitie: Annotated[ReceiveInteractive, Depends()],
        image: list[UploadFile]
):
    return {"status": "ok"}

# @router.post("/")
# async def creat_interactive(
#         interactivitie: Annotated[ReceiveInteractive, Depends()],
# ) -> InteractiveId:
#     user_id_role = await Repository.get_user_id_and_role_by_telegram_id(interactivitie.telegram_id)
#     if user_id_role is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#     if user_id_role.role != UserRoleEnum.leader:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can create interactives")
#
#     user_id = user_id_role.user_id
#     interactive = interactivitie.interactive
#
#     for i, question in enumerate(interactive.questions):
#         if question.position != i + 1:
#             raise HTTPException(status_code=400, detail=f"Question positions must be sequential starting from 1")
#         if len(question.answers) > 4:
#             raise HTTPException(status_code=400, detail=f"Too many answers for question {question.text}")
#         correct_answers = [a for a in question.answers if a.is_correct]
#         if len(correct_answers) != 1:
#             raise HTTPException(status_code=400,
#                                 detail=f"There must be exactly one correct answer in question {question.text}")
#
#     code = await Repository.generate_unique_code()
#
#     interactive_id = await Repository.create_interactive(
#         InteractiveCreate(
#             **interactive.model_dump(),
#             code=code,
#             created_by_id=user_id
#         )
#     )
#     return interactive_id
#

# @router.get("/me")
# async def get_me(
#         telegram_id: Annotated[TelegramId, Depends()],
# ) -> MyInteractives:
#     user_id = await Repository.get_user_id(telegram_id.telegram_id)
#     if user_id is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#     interactives_list_conducted = await Repository.get_interactives(user_id, conducted=True)
#     interactives_list_not_conducted = await Repository.get_interactives(user_id, conducted=False)
#
#     return MyInteractives(interactives_list_conducted=interactives_list_conducted,
#                           interactives_list_not_conducted=interactives_list_not_conducted)
#
#
# @router.get("/join")
# async def get_join_interactives(
#         code: Annotated[InteractiveCode, Depends()],
# ) -> InteractiveId:
#     interactive_id = await Repository.check_code_exists(code.code)
#     if interactive_id is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")
#     if interactive_id in ws_router.interactive_sessions:
#         if await ws_router.interactive_sessions[interactive_id].get_stage() != Stage.WAITING:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive started")
#     return InteractiveId(interactive_id=interactive_id)
#
#
# @router.get("/{interactive_id}")
# async def get_interactive(
#         interactive_id: Annotated[InteractiveId, Depends()],
#         telegram_id: Annotated[TelegramId, Depends()],
# ) -> Interactive:
#     user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
#     if user_id_role is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#     if user_id_role.role != UserRoleEnum.leader:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can get info interactives")
#
#     user_id = user_id_role.user_id
#
#     info = await Repository.get_all_interactive_info(user_id, interactive_id.interactive_id)
#     if info is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")
#
#     return info
#
#
# @router.patch("/{interactive_id}")
# async def patch_interactive(
#         interactive_id: Annotated[InteractiveId, Depends()],
#         telegram_id: Annotated[TelegramId, Depends()],
#         interactive: Interactive,
# ) -> InteractiveId:
#     user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
#     if user_id_role is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#     if user_id_role.role != UserRoleEnum.leader:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can patch interactives")
#
#     user_id = user_id_role.user_id
#
#     for i, question in enumerate(interactive.questions):
#         if question.position != i + 1:
#             raise HTTPException(status_code=400, detail=f"Question positions must be sequential starting from 1")
#         if len(question.answers) > 4:
#             raise HTTPException(status_code=400, detail=f"Too many answers for question {question.text}")
#         correct_answers = [a for a in question.answers if a.is_correct]
#         if len(correct_answers) != 1:
#             raise HTTPException(status_code=400,
#                                 detail=f"There must be exactly one correct answer in question {question.text}")
#
#     conducted = await Repository.get_interactive_conducted(interactive_id.interactive_id, user_id=user_id)
#
#     if conducted is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")
#
#     if conducted:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interactive already end")
#
#     if interactive_id.interactive_id in ws_router.interactive_sessions:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive started")
#
#     new_interactive_id = await Repository.update_interactive(interactive_id=interactive_id.interactive_id,
#                                                              data=interactive)
#
#     return new_interactive_id
#
#
# @router.delete("/{interactive_id}")
# async def delete_interactive(
#         interactive_id: Annotated[InteractiveId, Depends()],
#         telegram_id: Annotated[TelegramId, Depends()],
# ) -> InteractiveId:
#     user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
#     if user_id_role is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#     if user_id_role.role != UserRoleEnum.leader:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can patch interactives")
#
#     user_id = user_id_role.user_id
#
#     conducted = await Repository.get_interactive_conducted(interactive_id.interactive_id, user_id=user_id)
#
#     if conducted is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")
#
#     if conducted:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interactive already end")
#
#     if interactive_id.interactive_id in ws_router.interactive_sessions and conducted == False:
#         await ws_router.disconnect_delete(interactive_id.interactive_id)
#
#     else:
#         await Repository.remove_participant_from_interactive(interactive_id=interactive_id.interactive_id)
#
#     new_interactive_id = await Repository.delite_interactive(interactive_id=interactive_id.interactive_id)
#
#     return new_interactive_id
#
#
# @router.get("/is_running/{interactive_id}")
# async def is_running(interactive_id: Annotated[InteractiveId, Depends()]):
#     return interactive_id.interactive_id in ws_router.interactive_sessions
