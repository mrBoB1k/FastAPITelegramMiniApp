from users.schemas import UserRoleEnum
from websocket.InteractiveSession import InteractiveSession, Stage
from fastapi import WebSocket, WebSocketException
from websocket.repository import Repository
from websocket.schemas import LeaderSent, ParticipantSent, WebSocketConnection, CreateQuizParticipant, \
    QuestionType, StageWaiting, StageCountdown, StageQuestion, StageDiscussion, StageEnd, \
    DataAnswersStageDiscussionTypeOne, DataAnswersStageDiscussionTypeMany, DataAnswersStageDiscussionTypeTextLeader, \
    DataAnswersStageDiscussionTypeTextParticipantTrue, DataAnswersStageDiscussionTypeTextParticipantFalse, \
    StageDiscussionParticipant, CorrectAnswerStageDiscussionTypeTextLeader, StageEndParticipant, Winner, ScoreStageEnd


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
        if role != UserRoleEnum.participant:
            await websocket.accept()
            target_conn = next(
                (conn for conn in self.active_connections.get(interactive_id, []) if
                 conn.role == role and conn.user_id == user_id),
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
                 conn.role == role and conn.user_id == user_id),
                None
            )
            if target_conn:
                await websocket.accept()
                target_conn.websocket = websocket
            else:
                if await self.interactive_sessions[
                    interactive_id].get_stage() != Stage.WAITING and not await Repository.check_register_quiz_participant(
                    CreateQuizParticipant(user_id=user_id, interactive_id=interactive_id, total_time=0)):
                    raise WebSocketException(code=4003, reason="Interactive running now")
                else:
                    await websocket.accept()
                    self.active_connections[interactive_id].append(
                        WebSocketConnection(websocket=websocket, user_id=user_id, role=role))

    async def disconnect(self, interactive_id: int, user_id: int, role: UserRoleEnum):
        """Отключение вебсокета от интерактива"""
        if interactive_id in self.active_connections:
            if role != UserRoleEnum.participant and interactive_id in self.interactive_sessions and await \
                    self.interactive_sessions[interactive_id].get_stage() == Stage.WAITING:
                await self.interactive_sessions[interactive_id].stop()
            else:
                target_conn = next(
                    (conn for conn in self.active_connections.get(interactive_id, []) if
                     conn.role == role and conn.user_id == user_id),
                    None
                )
                if target_conn:
                    self.active_connections[interactive_id].remove(target_conn)

    async def _broadcast_callback(self, interactive_id: int,
                                  message: StageWaiting | StageCountdown | StageQuestion | StageDiscussion | StageEnd,
                                  stage: Stage, question_type: QuestionType | None = None):
        """Колбек для рассылки сообщений из InteractiveSession"""
        if interactive_id in self.active_connections:
            if stage == Stage.WAITING or stage == Stage.COUNTDOWN or stage == Stage.QUESTION:
                for data in self.active_connections[interactive_id]:
                    try:
                        await data.websocket.send_json(message.model_dump())
                    except:
                        await self.disconnect(interactive_id, data.user_id, data.role)
            elif stage == Stage.DISCUSSION and question_type is not None:
                if question_type == QuestionType.one:
                    persentages = await Repository.get_percentages(message.data.question.id)
                    id_correct_answer = await Repository.get_id_correct_answers(message.data.question.id)
                    data_answers = DataAnswersStageDiscussionTypeOne(id_correct_answer=id_correct_answer[0],
                                                                     percentages=persentages)
                    message.data_answers = data_answers
                    for data in self.active_connections[interactive_id]:
                        if data.role != UserRoleEnum.participant:
                            try:
                                await data.websocket.send_json(message.model_dump())
                            except:
                                await self.disconnect(interactive_id, data.user_id, data.role)
                        else:
                            try:
                                score = await Repository.get_user_score(data.user_id, interactive_id)
                                participant = StageDiscussionParticipant(**message.model_dump(), score=score)
                                await data.websocket.send_json(participant.model_dump())
                            except:
                                await self.disconnect(interactive_id, data.user_id, data.role)
                elif question_type == QuestionType.many:
                    persentages = await Repository.get_percentages(message.data.question.id)
                    id_correct_answer = await Repository.get_id_correct_answers(message.data.question.id)
                    data_answers = DataAnswersStageDiscussionTypeMany(id_correct_answer=id_correct_answer,
                                                                      percentages=persentages)
                    message.data_answers = data_answers
                    for data in self.active_connections[interactive_id]:
                        if data.role != UserRoleEnum.participant:
                            try:
                                await data.websocket.send_json(message.model_dump())
                            except:
                                await self.disconnect(interactive_id, data.user_id, data.role)
                        else:
                            try:
                                score = await Repository.get_user_score(data.user_id, interactive_id)
                                participant = StageDiscussionParticipant(**message.model_dump(), score=score)
                                await data.websocket.send_json(participant.model_dump())
                            except:
                                await self.disconnect(interactive_id, data.user_id, data.role)
                elif question_type == QuestionType.text:
                    persentages_text = await Repository.get_percentages_for_text(message.data.question.id)
                    for data in self.active_connections[interactive_id]:
                        if data.role != UserRoleEnum.participant:
                            try:
                                list_answer_data = [
                                    CorrectAnswerStageDiscussionTypeTextLeader(text=i.text, percentage=i.percentage) for
                                    i in persentages_text]
                                message.data_answers = DataAnswersStageDiscussionTypeTextLeader(
                                    correct_answers=list_answer_data)
                                await data.websocket.send_json(message.model_dump())
                            except:
                                await self.disconnect(interactive_id, data.user_id, data.role)
                        else:
                            is_correct = await Repository.is_user_answer_correct(data.user_id, message.data.question.id)
                            if is_correct:
                                try:
                                    score = await Repository.get_user_score(data.user_id, interactive_id)
                                    match = await Repository.get_user_matched_answer_id(data.user_id,
                                                                                        message.data.question.id)
                                    item = next((p for p in persentages_text if p.id == match), None)
                                    message.data_answers = DataAnswersStageDiscussionTypeTextParticipantTrue(
                                        is_correct=is_correct, answer=item.text, percentage=item.percentage)
                                    participant = StageDiscussionParticipant(**message.model_dump(), score=score)
                                    await data.websocket.send_json(participant.model_dump())
                                except:
                                    await self.disconnect(interactive_id, data.user_id, data.role)
                            else:
                                try:
                                    score = await Repository.get_user_score(data.user_id, interactive_id)
                                    list_answer_data = [
                                        CorrectAnswerStageDiscussionTypeTextLeader(text=i.text, percentage=i.percentage)
                                        for i in persentages_text]

                                    message.data_answers = DataAnswersStageDiscussionTypeTextParticipantFalse(
                                        is_correct=is_correct,
                                        answers=list_answer_data)
                                    participant = StageDiscussionParticipant(**message.model_dump(), score=score)
                                    await data.websocket.send_json(participant.model_dump())
                                except:
                                    await self.disconnect(interactive_id, data.user_id, data.role)
            elif stage == Stage.END:
                winners_sorted_list = await Repository.get_winners(interactive_id)
                winners = []
                winners_dict = {}
                for i, w in enumerate(winners_sorted_list):
                    winners.append(Winner(
                        position=i + 1,
                        username=w["username"],
                        score=w["score"],
                        time=w["total_time"]
                    ))
                    winners_dict[w["user_id"]] = ScoreStageEnd(
                        position=i + 1,
                        score=w["score"],
                        time=w["total_time"]
                    )
                message.data.winners = winners
                for data in self.active_connections[interactive_id]:
                    if data.role != UserRoleEnum.participant:
                        try:
                            await data.websocket.send_json(message.model_dump())
                        except:
                            await self.disconnect(interactive_id, data.user_id, data.role)
                    else:
                        try:
                            score = winners_dict[data.user_id]
                            participant = StageEndParticipant(**message.model_dump(), score=score)
                            await data.websocket.send_json(participant.model_dump())
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

        question_data = await self.interactive_sessions[interactive_id].get_question_data()
        if question_data is None:
            return

        answers_data = await self.interactive_sessions[interactive_id].get_answers_data()
        timer = await self.interactive_sessions[interactive_id].get_timer_passed()
        is_correct = False

        if question_data.type == QuestionType.one and participant.answer_id is not None:
            answers_id = [i.id for i in answers_data]
            try_answers_id = [i.id for i in answers_data if i.is_correct][0]

            if not (participant.answer_id in answers_id):
                return

            if participant.answer_id == try_answers_id:
                is_correct = True

            await Repository.put_user_answers(participant_id=participant_id, question_id=question_data.id,
                                              time=timer, is_correct=is_correct, question_type=QuestionType.one,
                                              answer_id=participant.answer_id)

        elif question_data.type == QuestionType.many and participant.answer_ids is not None:
            answers_id = [i.id for i in answers_data]
            try_answers_id = [i.id for i in answers_data if i.is_correct]
            set_participant_answer_ids = set(participant.answer_ids)

            if not (set_participant_answer_ids.issubset(answers_id)):
                return

            if set_participant_answer_ids == set(try_answers_id):
                is_correct = True

            await Repository.put_user_answers(participant_id=participant_id, question_id=question_data.id,
                                              time=timer, is_correct=is_correct, question_type=QuestionType.many,
                                              answer_ids=participant.answer_ids)

        elif question_data.type == QuestionType.text and participant.answer_text is not None:

            matched_answer_id = None
            for item in answers_data:
                if item.text.casefold() == participant.answer_text.casefold():
                    is_correct = True
                    matched_answer_id = item.id
                    break
            await Repository.put_user_answers(participant_id=participant_id, question_id=question_data.id,
                                              time=timer, is_correct=is_correct, question_type=QuestionType.text,
                                              answer_text=participant.answer_text, matched_answer_id=matched_answer_id)
        else:
            return

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
                await Repository.remove_participant_from_interactive(user_id=conn.user_id,
                                                                     interactive_id=interactive_id)

        await self.interactive_sessions[interactive_id].stop()
