from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Annotated

from dependencies import verify_key
from exceptions import InteractiveNotFoundWSException, InteractiveAlreadyEndWSException, UserNotFoundWSException, \
    UserAccessDeniedWSException
from models import UserRoleEnum
from users.repository import Repository as Repository_Users
from auth.router import get_current_active_token_ws
from auth.schemas import TokenData

from websocket.repository import Repository
from websocket.session_manager import SessionManager
from websocket.schemas import LeaderSent, ParticipantSent, CreateQuizParticipant

router = APIRouter(
    prefix="/ws",
    tags=["/ws"]
)

manager = SessionManager()


@router.websocket("/{interactive_id}", dependencies=[Depends(verify_key)])
async def websocket_endpoint(
        websocket: WebSocket,
        interactive_id: int,
        telegram_id: int,
        role: UserRoleEnum,
):
    role = UserRoleEnum.participant

    conducted = await Repository.get_interactive_conducted(interactive_id=interactive_id)
    if conducted is None:
        raise InteractiveNotFoundWSException()
    if conducted:
        raise InteractiveAlreadyEndWSException()

    user_id = await Repository_Users.get_user_id_by_telegram_id(telegram_id=telegram_id)
    if user_id is None:
        raise UserNotFoundWSException()

    await manager.connect(
        websocket=websocket,
        interactive_id=interactive_id,
        user_id=user_id,
        role=role
    )
    try:
        participant_id = await Repository.register_quiz_participant(
            CreateQuizParticipant(
                user_id=user_id,
                interactive_id=interactive_id,
                total_time=0
            )
        )
        while True:
            data = await websocket.receive_json()
            participant_sent = ParticipantSent(**data)
            await manager.handle_participant_message(
                participant=participant_sent,
                participant_id=participant_id,
                interactive_id=interactive_id
            )

    except WebSocketDisconnect:
        await manager.disconnect(
            interactive_id=interactive_id,
            user_id=user_id,
            role=role
        )
    except Exception as e:
        await manager.disconnect(
            interactive_id=interactive_id,
            user_id=user_id,
            role=role
        )


@router.websocket("/organization/{interactive_id}")
async def websocket_endpoint2(
        websocket: WebSocket,
        current_token: Annotated[TokenData, Depends(get_current_active_token_ws)],
        interactive_id: int,
):
    conducted = await Repository.get_interactive_conducted(interactive_id=interactive_id)
    if conducted is None:
        raise InteractiveNotFoundWSException()
    if conducted:
        raise InteractiveAlreadyEndWSException()

    creates_flag = await Repository.check_interactive_creates(
        interactive_id=interactive_id,
        organization_participant_id=current_token.participant_id
    )
    if not creates_flag:
        raise UserAccessDeniedWSException()

    await manager.connect(
        websocket=websocket,
        interactive_id=interactive_id,
        user_id=current_token.participant_id,
        role=current_token.role
    )
    try:
        while True:
            data = await websocket.receive_json()
            leader_sent = LeaderSent(**data)
            await manager.handle_leader_message(leader_sent=leader_sent, interactive_id=interactive_id)

    except WebSocketDisconnect:
        await manager.disconnect(
            interactive_id=interactive_id,
            user_id=current_token.participant_id,
            role=current_token.role
        )
    except Exception as e:
        await manager.disconnect(
            interactive_id=interactive_id,
            user_id=current_token.participant_id,
            role=current_token.role
        )
