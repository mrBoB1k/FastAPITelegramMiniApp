from pydantic import json
from websocket.InteractiveSession import InteractiveSession, Stage
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from websocket.repository import Repository
from websocket.schemas import LeaderSent, ParticipantSent, PutUserAnswers


# class SessionManager:
#     def __init__(self):
#         self.sessions: Dict[int, InteractiveSession] = {}
#
#     async def connect(self, interactive_id: int, websocket: WebSocket):
#         await websocket.accept()
#
#         if interactive_id not in self.sessions:
#             meta = await Repository.get_interactive_meta(interactive_id)
#             self.sessions[interactive_id] = InteractiveSession(meta)
#
#         session = self.sessions[interactive_id]
#         session.participants[websocket] = {}  # Можно добавить user info позже
#         await session.broadcast(f"New user joined! Total: {len(session.participants)}")
#
#         try:
#             while True:
#                 data = await websocket.receive_text()
#                 await session.handle_message(websocket, data)
#         except WebSocketDisconnect:
#             await self.disconnect(interactive_id, websocket)
#
#     async def disconnect(self, interactive_id: int, websocket: WebSocket):
#         session = self.sessions.get(interactive_id)
#         if session:
#             session.participants.pop(websocket, None)
#             await session.broadcast(f"User left! Total: {len(session.participants)}")


class SessionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}  # interactive_id : list [websocket]
        self.interactive_sessions: dict[int, InteractiveSession] = {}  # interactive_id : InteractiveSession

    async def connect(self, websocket: WebSocket, interactive_id: int):
        if interactive_id not in self.interactive_sessions:
            meta_data = await Repository.get_interactive_info(interactive_id)
            questions = await Repository.get_interactive_question(interactive_id)
            self.interactive_sessions[interactive_id] = InteractiveSession(meta_data, questions, self._broadcast_callback, self._get_participants_count)

        if await self.interactive_sessions[interactive_id].get_stage() != Stage.WAITING:
            raise WebSocketException(code=4003, reason="Interactive running now")

        await websocket.accept()
        if interactive_id not in self.active_connections:
            self.active_connections[interactive_id] = []
        self.active_connections[interactive_id].append(websocket)

    def disconnect(self, websocket: WebSocket, interactive_id: int):
        if interactive_id in self.active_connections and websocket in self.active_connections[interactive_id]:
            self.active_connections[interactive_id].remove(websocket)
    # async def send_personal_message(self, message: str, websocket: WebSocket):
    #     await websocket.send_text(message)

    async def _broadcast_callback(self, interactive_id: int, message: json):
        """Колбек для рассылки сообщений из InteractiveSession"""
        if interactive_id in self.active_connections:
            for websocket  in self.active_connections[interactive_id]:
                try:
                    await websocket.send_json(message)
                except:
                    self.disconnect(websocket, interactive_id)

    async def _get_participants_count(self, interactive_id: int) -> int:
        """Возвращает количество активных участников для указанного интерактива"""
        if interactive_id in self.active_connections:
            return len(self.active_connections[interactive_id])
        return 0

    async def handle_participant_message(self, participant: ParticipantSent, participant_id: int, interactive_id: int):
        if interactive_id not in self.interactive_sessions:
            return
        question_id = await self.interactive_sessions[interactive_id].get_question_id()
        if question_id == -1:
            return
        await Repository.put_user_answers(
            PutUserAnswers(question_id=question_id, participant_id=participant_id, answer_id=participant.answer_id))

    async def handle_leader_message(self, leader_sent: LeaderSent, interactive_id: int):
        if interactive_id not in self.interactive_sessions:
            return
        await self.interactive_sessions[interactive_id].change_status(leader_sent.interactive_status)

