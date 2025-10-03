from pydantic import json

from users.schemas import UserRoleEnum
from websocket.InteractiveSession import InteractiveSession, Stage
from fastapi import WebSocket, WebSocketException
from websocket.repository import Repository
from websocket.schemas import LeaderSent, ParticipantSent, PutUserAnswers, WebSocketConnection, CreateQuizParticipant


class SessionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocketConnection]] = {}  # interactive_id : list WebSocketConnection
        self.interactive_sessions: dict[int, InteractiveSession] = {}  # interactive_id : InteractiveSession

    async def connect(self, websocket: WebSocket, interactive_id: int, user_id: int, role: UserRoleEnum):
        """Создание интерактива, если его нет. Подключение вебсокета к интерактиву"""
        if interactive_id not in self.interactive_sessions:
            meta_data = await Repository.get_interactive_info(interactive_id)
            questions = await Repository.get_interactive_question(interactive_id)
            self.interactive_sessions[interactive_id] = InteractiveSession(meta_data, questions,
                                                                           self._broadcast_callback,
                                                                           self._get_participants_count_callback, self)
            self.active_connections[interactive_id] = []
            await self.interactive_sessions[interactive_id].start()

        # matching_connections = [conn for conn in self.active_connections.get(interactive_id, [])
        #                         if conn.user_id == user_id]

        # await websocket.accept()
        if role == UserRoleEnum.leader:
            await websocket.accept()
            target_conn = next(
                (conn for conn in self.active_connections.get(interactive_id, []) if
                 conn.role == UserRoleEnum.leader and conn.user_id == user_id),
                None
            )
            if target_conn:
                target_conn.websocket = websocket
            else:
                self.active_connections[interactive_id].append(
                    WebSocketConnection(websocket=websocket, user_id=user_id, role=role))

        else:
            target_conn = next(
                (conn for conn in self.active_connections.get(interactive_id, []) if
                 conn.role == UserRoleEnum.participant and conn.user_id == user_id),
                None
            )
            if target_conn:
                await websocket.accept()
                target_conn.websocket = websocket
            else:

                if await self.interactive_sessions[
                    interactive_id].get_stage() != Stage.WAITING and not await Repository.check_register_quiz_participant(
                        CreateQuizParticipant(user_id=user_id, interactive_id=interactive_id)):
                    raise WebSocketException(code=4003, reason="Interactive running now")
                else:
                    await websocket.accept()
                    self.active_connections[interactive_id].append(
                        WebSocketConnection(websocket=websocket, user_id=user_id, role=role))

    async def disconnect(self, interactive_id: int, user_id: int, role: UserRoleEnum):
        """Отключение вебсокета от интерактива"""
        if interactive_id in self.active_connections:
            if role == UserRoleEnum.leader and interactive_id in self.interactive_sessions and await self.interactive_sessions[interactive_id].get_stage() == Stage.WAITING:
                print('ливнул ведущий на стадий ожидания')
                await self.interactive_sessions[interactive_id].stop()
            else:
                target_conn = next(
                    (conn for conn in self.active_connections.get(interactive_id, []) if
                     conn.role == role and conn.user_id == user_id),
                    None
                )
                if target_conn:
                    self.active_connections[interactive_id].remove(target_conn)

    async def _broadcast_callback(self, interactive_id: int, message: json):
        """Колбек для рассылки сообщений из InteractiveSession"""
        if interactive_id in self.active_connections:
            for data in self.active_connections[interactive_id]:
                try:
                    await data.websocket.send_json(message)
                except:
                    await self.disconnect(interactive_id, data.user_id, data.role)

    async def _get_participants_count_callback(self, interactive_id: int) -> int:
        """Возвращает количество активных участников для указанного интерактива"""
        if interactive_id in self.active_connections:
            return len(self.active_connections[interactive_id]) - 1
        return 0

    async def handle_participant_message(self, participant: ParticipantSent, participant_id: int, interactive_id: int):
        """Обработка действий участика, запись его ответа в бд"""
        if interactive_id not in self.interactive_sessions:
            return
        question_id = await self.interactive_sessions[interactive_id].get_question_id()
        if question_id == -1:
            return

        answers_id = await self.interactive_sessions[interactive_id].get_id_answers()

        if not (participant.answer_id in answers_id):
            return

        await Repository.put_user_answers(
            PutUserAnswers(question_id=question_id, participant_id=participant_id, answer_id=participant.answer_id))

    async def handle_leader_message(self, leader_sent: LeaderSent, interactive_id: int):
        """Обработка действий ведущего, смена статуса интерактива"""
        if interactive_id not in self.interactive_sessions:
            return
        await self.interactive_sessions[interactive_id].change_status(leader_sent.interactive_status)

    async def remove_session(self, interactive_id: int):
        if interactive_id in self.interactive_sessions:
            self.interactive_sessions.pop(interactive_id)

        if interactive_id in self.active_connections:
            self.active_connections.pop(interactive_id)

    async def disconnect_delete(self, interactive_id: int):
        for conn in self.active_connections.pop(interactive_id):
            await conn.websocket.close()
            if conn.role == UserRoleEnum.participant:
                await Repository.remove_participant_from_interactive(user_id=conn.user_id, interactive_id=interactive_id)

        await self.interactive_sessions[interactive_id].stop()
