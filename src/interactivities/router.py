from fastapi import APIRouter, UploadFile, Form, File, Depends
from typing import Annotated, List, Optional
import json

from dependencies import verify_key
from exceptions import InteractiveParsingException, InvalidQuestionPositionsException, InvalidQuestionScoreException, \
    TooManyAnswersException, RequiresOneCorrectAnswerException, RequiresManyCorrectAnswerException, \
    RequiresTextCorrectAnswerException, InsufficientImageException, FileSizeExceededException, \
    InvalidContentTypeException, InvalidRangeNumbersException, InteractiveNotFoundException, \
    InteractiveAlreadyStartedException, InteractiveAlreadyEndException, LeaderCannotDeleteForeignInteractiveException, \
    CannotDeleteForeignOrganizationInteractiveException, CannotAccessForeignOrganizationInteractiveException
from users.schemas import UserRoleEnum
from websocket.router import manager as ws_manager
from websocket.InteractiveSession import Stage
from websocket.schemas import StageEnd, DataStageEnd, Winner
from websocket.repository import Repository as Repository_Websocket
import minios3.services as services
from organizations.repository import Repository as Repository_Organization
from auth.router import get_current_active_token
from auth.schemas import TokenData

from interactivities.schemas import InteractiveId, InteractiveCreate, MyInteractive, InteractiveCode, Interactive, \
    InteractiveType, MinioData, GetDataInteractive
from interactivities.repository import Repository

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
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        interactive: str = Form(..., description="JSON объекта `Interactive`"),
        images: Optional[List[UploadFile]] = File(default=None, description="Список изображений (может отсутствовать)"),
) -> InteractiveId:
    try:
        interactive_data = json.loads(interactive)
        interactive = Interactive(**interactive_data)
    except Exception as e:
        raise InteractiveParsingException()

    count_images = 0

    for i, question in enumerate(interactive.questions):
        if question.position != i + 1:
            raise InvalidQuestionPositionsException()

        count_answers = len(question.answers)

        if question.score < 1 or question.score > 5:
            raise InvalidQuestionScoreException()

        if question.image is not None and question.image == "image":
            count_images += 1

        if question.type == InteractiveType.one:
            if count_answers > 5 or count_answers == 0:
                raise TooManyAnswersException(question_text=question.text, question_type=question.type)
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != 1:
                raise RequiresOneCorrectAnswerException(question_text=question.text, question_type=question.type)

        if question.type == InteractiveType.many:
            if count_answers > 5 or count_answers == 0:
                raise TooManyAnswersException(question_text=question.text, question_type=question.type)
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers < 2:
                raise RequiresManyCorrectAnswerException(question_text=question.text, question_type=question.type)

        if question.type == InteractiveType.text:
            if count_answers > 3 or count_answers == 0:
                raise TooManyAnswersException(question_text=question.text, question_type=question.type)
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != count_answers:
                raise RequiresTextCorrectAnswerException(question_text=question.text, question_type=question.type)

    images_data_first = []
    images_data_second = []
    if images is None and count_images > 0:
        raise InsufficientImageException()
    if images is not None:
        if count_images != len(images):
            raise InsufficientImageException()

        for image in images:

            file_size = image.size
            content_type = image.content_type

            if file_size > MAX_FILE_SIZE:
                raise FileSizeExceededException()

            # Проверка, что это изображение
            if not content_type or not content_type.startswith("image/"):
                raise InvalidContentTypeException(content_type=content_type)

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
            unique_filename = await Repository.generate_unique_filename(ext=ext, bucket_name="images")
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
                size=image_data_first.size,
                bucket_name="images"
            )
            images_data_second.append(image_data_second)

    code = await Repository.generate_unique_code()

    interactive_id = await Repository.create_interactive(
        data=InteractiveCreate(
            **interactive.model_dump(),
            code=code,
            created_by_id=current_token.participant_id
        ),
        images=images_data_second
    )
    return interactive_id


@router.get("/me")
async def get_me(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        data: Annotated[GetDataInteractive, Depends()],
) -> MyInteractive:
    if data.from_number < 0 or data.to_number < 0 or data.to_number < data.from_number:
        raise InvalidRangeNumbersException(from_number=data.from_number, to_number=data.to_number)

    result = await Repository.get_interactives(
        organization_id=current_token.organization_id,
        organization_participant_id=current_token.participant_id,
        filter=data.filter,
        from_number=data.from_number,
        to_number=data.to_number
    )
    return result


@router.get("/join", dependencies=[Depends(verify_key)])
async def get_join_interactive(
        code: Annotated[InteractiveCode, Depends()]
) -> InteractiveId:
    interactive_id = await Repository.check_code_exists(code=code.code)
    if interactive_id is None:
        raise InteractiveNotFoundException()

    if interactive_id in ws_manager.interactive_sessions:
        if await ws_manager.interactive_sessions[interactive_id].get_stage() != Stage.WAITING:
            raise InteractiveAlreadyStartedException()

    return InteractiveId(interactive_id=interactive_id)


@router.get("/{interactive_id}")
async def get_interactive(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        interactive_id: Annotated[InteractiveId, Depends()],
) -> Interactive:
    info = await Repository.get_all_interactive_info(
        organization_id=current_token.organization_id,
        interactive_id=interactive_id.interactive_id
    )

    if info is None:
        raise InteractiveNotFoundException()

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
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        interactive_id: int = Annotated[InteractiveId, Depends()],
        interactive: str = Form(..., description="JSON объекта `Interactive`"),
        images: Optional[List[UploadFile]] = File(default=None, description="Список изображений (может отсутствовать)")
) -> InteractiveId:
    try:
        interactive_data = json.loads(interactive)
        interactive = Interactive(**interactive_data)
    except Exception as e:
        raise InteractiveParsingException()

    conducted = await Repository.get_interactive_conducted(
        interactive_id=interactive_id,
        organization_participant_id=current_token.participant_id
    )

    if conducted is None:
        raise InteractiveNotFoundException()
    if conducted:
        raise InteractiveAlreadyEndException()
    if interactive_id in ws_manager.interactive_sessions:
        raise InteractiveAlreadyStartedException()

    count_images = 0
    for i, question in enumerate(interactive.questions):
        if question.position != i + 1:
            raise InvalidQuestionPositionsException()

        count_answers = len(question.answers)
        if question.score < 1 or question.score > 5:
            raise InvalidQuestionScoreException()
        if question.image is not None and question.image == "image":
            count_images += 1

        if question.type == InteractiveType.one:
            if count_answers > 5 or count_answers == 0:
                raise TooManyAnswersException(question_text=question.text, question_type=question.type)
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != 1:
                raise RequiresOneCorrectAnswerException(question_text=question.text, question_type=question.type)

        if question.type == InteractiveType.many:
            if count_answers > 5 or count_answers == 0:
                raise TooManyAnswersException(question_text=question.text, question_type=question.type)
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers < 2:
                raise RequiresManyCorrectAnswerException(question_text=question.text, question_type=question.type)

        if question.type == InteractiveType.text:
            if count_answers > 3 or count_answers == 0:
                raise TooManyAnswersException(question_text=question.text, question_type=question.type)
            correct_answers = [a for a in question.answers if a.is_correct]
            count_correct_answers = len(correct_answers)
            if count_correct_answers != count_answers:
                raise RequiresTextCorrectAnswerException(question_text=question.text, question_type=question.type)

    images_data_first = []
    images_data_second = []
    if images is None and count_images > 0:
        raise InsufficientImageException()
    if images is not None:
        if count_images != len(images):
            raise InsufficientImageException()

        for image in images:

            file_size = image.size
            content_type = image.content_type

            if file_size > MAX_FILE_SIZE:
                raise FileSizeExceededException()

            # Проверка, что это изображение
            if not content_type or not content_type.startswith("image/"):
                raise InvalidContentTypeException(content_type=content_type)

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
            unique_filename = await Repository.generate_unique_filename(
                ext=ext,
                bucket_name="images"
            )
            filename = image.filename

            data = MinioData(
                file=await image.read(),
                filename=filename,
                unique_filename=unique_filename,
                content_type=content_type,
                size=file_size
            )

            images_data_first.append(data)

        for image_data_first in images_data_first:
            image_data_second = await services.save_image_to_minio(
                file=image_data_first.file,
                filename=image_data_first.filename,
                unique_filename=image_data_first.unique_filename,
                content_type=image_data_first.content_type,
                size=image_data_first.size,
                bucket_name="images"
            )
            images_data_second.append(image_data_second)

    new_interactive_id = await Repository.update_interactive(
        interactive_id=interactive_id,
        data=interactive,
        images=images_data_second
    )
    return new_interactive_id


@router.delete("/{interactive_id}")
async def delete_interactive(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        interactive_id: Annotated[InteractiveId, Depends()],
) -> InteractiveId:
    interactive_info = await Repository.get_interactive_info(interactive_id=interactive_id.interactive_id)
    if interactive_info is None:
        raise InteractiveNotFoundException()

    if interactive_info.created_by_id != current_token.participant_id:
        if current_token.role == UserRoleEnum.leader:
            raise LeaderCannotDeleteForeignInteractiveException()
        else:
            data_creator = await Repository_Organization.get_name_role_organization_id_by_organization_participant_id(
                participant_id=interactive_info.created_by_id
            )
            if data_creator.organization_id != current_token.organization_id:
                raise CannotDeleteForeignOrganizationInteractiveException()

    if interactive_info.conducted:
        raise InteractiveAlreadyEndException()

    if interactive_id.interactive_id in ws_manager.interactive_sessions:
        await ws_manager.disconnect_delete(interactive_id.interactive_id)
    else:
        await Repository.remove_participant_from_interactive(interactive_id=interactive_id.interactive_id)

    new_interactive_id = await Repository.delite_interactive(interactive_id=interactive_id.interactive_id)

    return new_interactive_id


@router.get("/is_running/{interactive_id}")
async def is_running(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        interactive_id: Annotated[InteractiveId, Depends()]
):
    return interactive_id.interactive_id in ws_manager.interactive_sessions


@router.get("/end/{interactive_id}")
async def get_interactive(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        interactive_id: Annotated[InteractiveId, Depends()],
) -> StageEnd:
    interactive_created_by_id = await Repository.get_interactive_created_by_id(interactive_id.interactive_id)
    if interactive_created_by_id is None:
        raise InteractiveNotFoundException()

    organization_id_who_created = await Repository_Organization.get_name_role_organization_id_by_organization_participant_id(
        participant_id=interactive_created_by_id
    )

    if organization_id_who_created.organization_id != current_token.organization_id:
        raise CannotAccessForeignOrganizationInteractiveException()

    title = await Repository.get_interactive_title(interactive_id=interactive_id.interactive_id)
    if title is None:
        raise InteractiveNotFoundException()

    participants_total = await Repository_Websocket.get_participant_count(interactive_id.interactive_id)
    winners_sorted_list = await Repository_Websocket.get_winners(interactive_id.interactive_id)
    winners = []
    for i, w in enumerate(winners_sorted_list):
        winners.append(Winner(
            position=i + 1,
            username=w["username"],
            score=w["score"],
            time=w["total_time"],
            participant_id=w["participant_id"],
            is_hidden=w["is_hidden"]
        ))

    data = DataStageEnd(title=title, participants_total=participants_total, winners=winners)
    result = StageEnd(stage=Stage.END, data=data)

    return result
