from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from websocket.repository import Repository
from users.schemas import UserRoleEnum
from websocket.session_manager import SessionManager
from websocket.schemas import LeaderSent, ParticipantSent, CreateQuizParticipant

router = APIRouter(
    prefix="/ws",
    tags=["/ws"]
)

manager = SessionManager()

@router.websocket("/{interactive_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        interactive_id: int,
        telegram_id: int,
        role: UserRoleEnum,
):
    if not await Repository.check_interactive(interactive_id):
        raise WebSocketException(code=4003, reason="Interactive not found")

    if await Repository.get_interactive_conducted(interactive_id):
        raise WebSocketException(code=4003, reason="Interactive already end")

    user_id = await Repository.get_user_id(telegram_id)
    if user_id is None:
        raise WebSocketException(code=4003, reason="User not found")

    if role == UserRoleEnum.leader and not (await Repository.check_interactive_creates(interactive_id, user_id)):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="User does not have access")

    await manager.connect(websocket, interactive_id, user_id, role)
    try:
        if role == UserRoleEnum.leader:
            while True:
                data = await websocket.receive_json()
                leader_sent = LeaderSent(**data)
                await manager.handle_leader_message(leader_sent, interactive_id)

        else:
            participant_id = await Repository.register_quiz_participant(
                CreateQuizParticipant(user_id=user_id, interactive_id=interactive_id))
            while True:
                data = await websocket.receive_json()
                participant_sent = ParticipantSent(**data)
                await manager.handle_participant_message(participant_sent, participant_id, interactive_id)

    except WebSocketDisconnect:
        await manager.disconnect(interactive_id, user_id, role)
    except Exception as e:
        await manager.disconnect(interactive_id, user_id, role)
