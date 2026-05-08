from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Annotated

from exceptions import InteractiveNotFoundWSException, InteractiveAlreadyEndWSException, UserAccessDeniedWSException
from models import UserRoleEnum
from auth.router import get_current_active_token_ws, get_current_active_token_for_participant_ws
from auth.schemas import TokenData, ParticipantTokenData

from websocket.moderation_manager import ModerationManager
from websocket.repository import Repository
from websocket.session_manager import SessionManager
from websocket.schemas import LeaderSent, ParticipantSent, CreateQuizParticipant, ModerationSent

router = APIRouter(
    prefix="/ws",
    tags=["/ws"]
)

moderation_manager = ModerationManager()
manager = SessionManager(moderation_manager=moderation_manager)

@router.websocket("/{interactive_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        current_token: Annotated[ParticipantTokenData, Depends(get_current_active_token_for_participant_ws)],
        interactive_id: int,
):
    role = UserRoleEnum.participant

    conducted = await Repository.get_interactive_conducted(interactive_id=interactive_id)
    if conducted is None:
        raise InteractiveNotFoundWSException()
    if conducted:
        raise InteractiveAlreadyEndWSException()

    block_participant = await Repository.get_blocket_participant(interactive_id=interactive_id, user_id=current_token.user_id)
    if block_participant is not None:
        message = await manager.get_waiting_stage_to_blocked(interactive_id=interactive_id)
        await websocket.accept()
        try:
            await websocket.send_json(message.model_dump())
        except:
            return
        await websocket.close(
            code=4006,
            reason='{"detail":{"message": "You have been removed from the interactive","code": "YOU_BEEN_REMOVED"}}'
        )

    await manager.connect(
        websocket=websocket,
        interactive_id=interactive_id,
        user_id=current_token.user_id,
        role=role
    )
    try:
        participant_data = await Repository.register_quiz_participant(
            user_id=current_token.user_id,
            interactive_id=interactive_id,
            total_time=0
        )
        participant_id = participant_data.id
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
            user_id=current_token.user_id,
            role=role
        )
    except Exception as e:
        await manager.disconnect(
            interactive_id=interactive_id,
            user_id=current_token.user_id,
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

@router.websocket("/moderation/{interactive_id}")
async def websocket_endpoint3(
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

    await moderation_manager.connect(interactive_id=interactive_id, websocket=websocket)
    await moderation_manager.broadcast(interactive_id=interactive_id)
    try:
        while True:
            data = await websocket.receive_json()
            moderation_sent = ModerationSent(**data)
            if moderation_sent.hide is not None:
                await manager.handle_leader_message(leader_sent=LeaderSent(hide=moderation_sent.hide), interactive_id=interactive_id)
            elif moderation_sent.block is not None:
                await manager.handle_moderation_block_participant(block_participant_id=moderation_sent.block, interactive_id=interactive_id)

    except WebSocketDisconnect:
        await moderation_manager.disconnect(
            interactive_id=interactive_id
        )
    except Exception as e:
        await moderation_manager.disconnect(
            interactive_id=interactive_id
        )