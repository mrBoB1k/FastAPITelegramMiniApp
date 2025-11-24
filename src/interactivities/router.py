from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File
from typing import Annotated, List, Optional
import json
from pydantic import ValidationError

from interactivities.schemas import ReceiveInteractive, InteractiveId, InteractiveCreate, MyInteractives, TelegramId, \
    InteractiveCode, Interactive, InteractiveType, MinioData, GetDataInteractive
from interactivities.repository import Repository

from users.schemas import UserRoleEnum

from websocket.router import manager as ws_manager
from websocket.InteractiveSession import Stage
from websocket.schemas import StageEnd, DataStageEnd, Winner
from websocket.repository import Repository as Repository_Websocket


import minios3.services as services

router = APIRouter(
    prefix="/api/interactivities",
    tags=["/api/interactivities"]
)

MAX_FILE_SIZE = 5 * 1024 * 1024


@router.post(
    "/",
    summary="Создание интерактива",
    description=(
            "Создаёт новый интерактив.\n\n"
            "⚠️ Поле `interactivitie` должно содержать JSON, соответствующий схеме `Interactive`.\n\n"
            "🧩 Пример:\n"
            f"```json\n{json.dumps(Interactive.Config.json_schema_extra['example'], ensure_ascii=False, indent=2)}\n```"
    )
)
async def creat_interactive(
        telegram_id: int = Form(..., description="ID пользователя Telegram"),
        interactive: str = Form(..., description="JSON объекта `Interactive`"),
        images: Optional[List[UploadFile]] = File(default=None, description="Список изображений (может отсутствовать)")
) -> InteractiveId:
    try:
        interactive_data = json.loads(interactive)
        interactive = Interactive(**interactive_data)
    except Exception as e:
        return {"error": str(e)}

    user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id_role.role != UserRoleEnum.leader:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can create interactives")

    user_id = user_id_role.user_id

    count_images = 0

    for i, question in enumerate(interactive.questions):
        if question.position != i + 1:
            raise HTTPException(status_code=400, detail=f"Question positions must be sequential starting from 1")

        count_answers = len(question.answers)

        if question.score < 1 or question.score > 5:
            raise HTTPException(status_code=400, detail=f"Question score must be between 1 and 5")

        if question.image is not None and question.image == "image":
            count_images += 1

        if question.type == InteractiveType.one:
            if count_answers > 5 or count_answers == 0:
                raise HTTPException(status_code=400,
                                    detail=f"Too many answers for question {question.text} of type {question.type}")
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != 1:
                raise HTTPException(status_code=400,
                                    detail=f"There must be one correct answer in a question {question.text} of type {question.type}.")

        if question.type == InteractiveType.many:
            if count_answers > 5 or count_answers == 0:
                raise HTTPException(status_code=400,
                                    detail=f"Too many answers for question {question.text} of type {question.type}")
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers < 2:
                raise HTTPException(status_code=400,
                                    detail=f"A question {question.text} of type {question.type} must have more than one correct answer.")

        if question.type == InteractiveType.text:
            if count_answers > 3 or count_answers == 0:
                raise HTTPException(status_code=400,
                                    detail=f"Too many answers for question {question.text} of type {question.type}")
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != count_answers:
                raise HTTPException(status_code=400,
                                    detail=f"A question {question.text} of type {question.type} all answers must be correct")

    images_data_first = []
    images_data_second = []
    if images is None and count_images > 0:
        raise HTTPException(status_code=400, detail="fewer images were received than expected")
    if images is not None:
        if count_images != len(images):
            raise HTTPException(status_code=400, detail="fewer images were received than expected")

        for image in images:

            file_size = image.size
            content_type = image.content_type

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File size exceeds 5 MB limit"
                )

            # Проверка, что это изображение
            if not content_type or not content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid content type: {content_type}. Only images are allowed."
                )

            # Определяем расширение из MIME-типа
            mime_to_ext = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/gif": "gif",
                "image/webp": "webp",
                "image/bmp": "bmp",
                "image/tiff": "tiff",
                "image/svg+xml": "svg"
            }
            ext = mime_to_ext.get(content_type, "bin")

            # Генерируем уникальное имя файла
            unique_filename = await Repository.generate_unique_filename(ext)
            filename = image.filename

            data = MinioData(file=await image.read(), filename=filename, unique_filename=unique_filename,
                             content_type=content_type, size=file_size)

            images_data_first.append(data)

        for image_data_first in images_data_first:
            image_data_second = await services.save_image_to_minio(
                file=image_data_first.file,
                filename=image_data_first.filename,
                unique_filename=image_data_first.unique_filename,
                content_type=image_data_first.content_type,
                size=image_data_first.size
            )
            images_data_second.append(image_data_second)

    code = await Repository.generate_unique_code()

    interactive_id = await Repository.create_interactive(
        data=InteractiveCreate(
            **interactive.model_dump(),
            code=code,
            created_by_id=user_id
        ),
        images=images_data_second
    )
    return interactive_id


@router.get("/me")
async def get_me(
        data: Annotated[GetDataInteractive, Depends()],
) -> MyInteractives:
    if data.from_number < 0 or data.to_number < 0 or data.to_number < data.from_number:
        raise HTTPException(status_code=404,
                            detail=f"Invalid input data: from_number {data.from_number} and to_number {data.to_number} are invalid")

    user_id = await Repository.get_user_id(data.telegram_id)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await Repository.get_interactives(user_id=user_id, filter=data.filter, from_number=data.from_number,
                                               to_number=data.to_number)
    return result


@router.get("/join")
async def get_join_interactives(
        code: Annotated[InteractiveCode, Depends()],
) -> InteractiveId:
    interactive_id = await Repository.check_code_exists(code.code)
    if interactive_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")
    if interactive_id in ws_manager.interactive_sessions:
        if await ws_manager.interactive_sessions[interactive_id].get_stage() != Stage.WAITING:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive started")
    return InteractiveId(interactive_id=interactive_id)


@router.get("/{interactive_id}")
async def get_interactive(
        interactive_id: Annotated[InteractiveId, Depends()],
        telegram_id: Annotated[TelegramId, Depends()],
) -> Interactive:
    user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id_role.role != UserRoleEnum.leader:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can get info interactives")

    user_id = user_id_role.user_id

    info = await Repository.get_all_interactive_info(user_id, interactive_id.interactive_id)
    if info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")

    return info


@router.patch(
    "/{interactive_id}",
    summary="Редактирование интерактива",
    description=(
            "Редактирует существующий интерактив.\n\n"
            "⚠️ Поле `interactivitie` должно содержать JSON, соответствующий схеме `Interactive`.\n\n"
            "🧩 Пример:\n"
            f"```json\n{json.dumps(Interactive.Config.json_schema_extra['example'], ensure_ascii=False, indent=2)}\n```"
    )
)
async def patch_interactive(
        interactive_id: int = Annotated[InteractiveId, Depends()],
        telegram_id: int = Form(..., description="ID пользователя Telegram"),
        interactive: str = Form(..., description="JSON объекта `Interactive`"),
        images: Optional[List[UploadFile]] = File(default=None, description="Список изображений (может отсутствовать)")
) -> InteractiveId:
    try:
        interactive_data = json.loads(interactive)
        interactive = Interactive(**interactive_data)
    except Exception as e:
        return {"error": str(e)}

    user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id_role.role != UserRoleEnum.leader:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can patch interactives")

    user_id = user_id_role.user_id

    count_images = 0

    for i, question in enumerate(interactive.questions):
        if question.position != i + 1:
            raise HTTPException(status_code=400, detail=f"Question positions must be sequential starting from 1")

        count_answers = len(question.answers)

        if question.score < 1 or question.score > 5:
            raise HTTPException(status_code=400, detail=f"Question score must be between 1 and 5")

        if question.image is not None and question.image == "image":
            count_images += 1

        if question.type == InteractiveType.one:
            if count_answers > 5 or count_answers == 0:
                raise HTTPException(status_code=400,
                                    detail=f"Too many answers for question {question.text} of type {question.type}")
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != 1:
                raise HTTPException(status_code=400,
                                    detail=f"There must be one correct answer in a question {question.text} of type {question.type}.")

        if question.type == InteractiveType.many:
            if count_answers > 5 or count_answers == 0:
                raise HTTPException(status_code=400,
                                    detail=f"Too many answers for question {question.text} of type {question.type}")
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers < 2:
                raise HTTPException(status_code=400,
                                    detail=f"A question {question.text} of type {question.type} must have more than one correct answer.")

        if question.type == InteractiveType.text:
            if count_answers > 3 or count_answers == 0:
                raise HTTPException(status_code=400,
                                    detail=f"Too many answers for question {question.text} of type {question.type}")
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != count_answers:
                raise HTTPException(status_code=400,
                                    detail=f"A question {question.text} of type {question.type} all answers must be correct")

    images_data_first = []
    images_data_second = []
    if images is None and count_images > 0:
        raise HTTPException(status_code=400, detail="fewer images were received than expected")
    if images is not None:
        if count_images != len(images):
            raise HTTPException(status_code=400, detail="fewer images were received than expected")

        for image in images:

            file_size = image.size
            content_type = image.content_type

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File size exceeds 5 MB limit"
                )

            # Проверка, что это изображение
            if not content_type or not content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid content type: {content_type}. Only images are allowed."
                )

            # Определяем расширение из MIME-типа
            mime_to_ext = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/gif": "gif",
                "image/webp": "webp",
                "image/bmp": "bmp",
                "image/tiff": "tiff",
                "image/svg+xml": "svg"
            }
            ext = mime_to_ext.get(content_type, "bin")

            # Генерируем уникальное имя файла
            unique_filename = await Repository.generate_unique_filename(ext)
            filename = image.filename

            data = MinioData(file=await image.read(), filename=filename, unique_filename=unique_filename,
                             content_type=content_type, size=file_size)

            images_data_first.append(data)

        for image_data_first in images_data_first:
            image_data_second = await services.save_image_to_minio(
                file=image_data_first.file,
                filename=image_data_first.filename,
                unique_filename=image_data_first.unique_filename,
                content_type=image_data_first.content_type,
                size=image_data_first.size
            )
            images_data_second.append(image_data_second)

    conducted = await Repository.get_interactive_conducted(interactive_id=interactive_id, user_id=user_id)

    if conducted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")

    if conducted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interactive already end")

    if interactive_id in ws_manager.interactive_sessions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive started")

    new_interactive_id = await Repository.update_interactive(interactive_id=interactive_id,
                                                             data=interactive,
                                                             images=images_data_second
                                                             )
    return new_interactive_id


@router.delete("/{interactive_id}")
async def delete_interactive(
        interactive_id: Annotated[InteractiveId, Depends()],
        telegram_id: Annotated[TelegramId, Depends()],
) -> InteractiveId:
    user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id_role.role != UserRoleEnum.leader:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can patch interactives")

    user_id = user_id_role.user_id

    conducted = await Repository.get_interactive_conducted(interactive_id.interactive_id, user_id=user_id)

    if conducted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interactive not found")

    if conducted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interactive already end")

    if interactive_id.interactive_id in ws_manager.interactive_sessions and conducted == False:
        await ws_manager.disconnect_delete(interactive_id.interactive_id)

    else:
        await Repository.remove_participant_from_interactive(interactive_id=interactive_id.interactive_id)

    new_interactive_id = await Repository.delite_interactive(interactive_id=interactive_id.interactive_id)

    return new_interactive_id


@router.get("/is_running/{interactive_id}")
async def is_running(interactive_id: Annotated[InteractiveId, Depends()]):
    return interactive_id.interactive_id in ws_manager.interactive_sessions


@router.get("/end/{interactive_id}")
async def get_interactive(
        interactive_id: Annotated[InteractiveId, Depends()],
        telegram_id: Annotated[TelegramId, Depends()],
) -> StageEnd:
    user_id_role = await Repository.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id_role.role != UserRoleEnum.leader:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only leaders can get end info interactive")

    user_id = user_id_role.user_id

    title = await Repository.get_interactive_title(interactive_id=interactive_id.interactive_id, user_id=user_id)
    if title is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Interactive not found or interactive not conducted")

    participants_total = await Repository_Websocket.get_participant_count(interactive_id.interactive_id)

    winners_sorted_list = await Repository_Websocket.get_winners(interactive_id.interactive_id)
    winners = []
    for i, w in enumerate(winners_sorted_list):
        winners.append(Winner(
            position=i + 1,
            username=w["username"],
            score=w["score"],
            time=w["total_time"]
        ))

    data = DataStageEnd(title=title, participants_total=participants_total, winners=winners)
    result = StageEnd(stage=Stage.END, data=data)

    return result
