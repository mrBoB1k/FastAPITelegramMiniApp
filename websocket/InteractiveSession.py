from typing import List, Dict, Optional, Callable, Any
import asyncio
from enum import Enum
from datetime import datetime
from websocket.schemas import InteractiveInfo, InteractiveStatus, Question, StageCountdown, DataStageCountdown, \
    DataStageQuestion, StageQuestion, DataStageDiscussion, StageDiscussion, DataStageEnd, StageEnd, DataStageWaiting, \
    StageWaiting
from websocket.repository import Repository
import json


class Stage(str, Enum):
    WAITING = "waiting"
    COUNTDOWN = "countdown"
    QUESTION = "question"
    DISCUSSION = "discussion"
    END = "end"
    PAUSE = "pause"


class InteractiveSession:
    def __init__(self, meta_data: InteractiveInfo, questions: List[Question],
                 broadcast_callback: Callable[[int, str], Any],
                 get_participants_count: Callable[[int], int]):
        self.interactive_id: int = meta_data.interactive_id  # из бд
        self.code: str = meta_data.code  # из бд
        self.title: str = meta_data.title  # из бд
        self.description: str = meta_data.description  # из бд
        self.answer_duration: int = meta_data.answer_duration  # из бд
        self.discussion_duration: int = meta_data.discussion_duration  # из бд
        self.countdown_duration: int = meta_data.countdown_duration  # из бд

        self.stage: Stage = Stage.WAITING  # фаза, нужна для обработки логики

        self.time_task: asyncio.Task | None = asyncio.create_task(self.waiting_timer())
        self.timer_duration: int = 0  # таймер изначально, на текущей фазе
        self.remaining_time: int = 0  # оставшееся время, на текущей фазе

        self.paused: bool = False  # пауза, нужна для обрабки логики
        self.waiting_timer_flag: bool = True
        self.second_step: int = 1

        self.question_index: int = 0  # текущий вопрос
        self.questions: List[Question] = questions
        self.current_question: Question | None = questions[0]

        self.get_participants_count = get_participants_count
        self.broadcast_callback = broadcast_callback

    async def get_stage(self) -> Stage:
        return self.stage

    async def get_question_id(self) -> int:
        if self.current_question:
            return self.current_question.id
        return -1

    async def _change_question(self):
        if self.question_index >= len(self.questions) - 1:
            await self._end_interactive_all()
            return
        self.question_index += 1
        self.current_question = self.questions[self.question_index]
        return

    async def change_status(self, interactive_status: InteractiveStatus):
        if interactive_status == InteractiveStatus.pause:
            await self._toggle_pause()
        elif interactive_status == InteractiveStatus.going:
            await self._start_interactive()
        elif interactive_status == InteractiveStatus.end:
            await self._end_interactive()

    async def _toggle_pause(self):
        if self.stage == Stage.WAITING or self.stage == Stage.END:
            return
        self.paused = not self.paused
        if self.paused:
            self.second_step = 0
        else:
            self.second_step = 1

    async def _start_interactive(self):
        if self.stage != Stage.WAITING:
            return
        self.waiting_timer_flag = False

    async def _end_interactive(self):
        await self._change_stage(Stage.END)

    async def _change_stage(self, new_stage: Stage):
        self.stage = new_stage
        if self.time_task is not None:
            self.time_task.cancel()
            try:
                await self.time_task
            except asyncio.CancelledError:
                pass
        self.time_task = None

        if new_stage == Stage.COUNTDOWN:
            self.timer_duration = self.countdown_duration
            self.remaining_time = self.countdown_duration
            self.time_task = asyncio.create_task(self.countdonw_timer())
            # await self._start_timer(self.timer_duration)
            # await self._wait_for_timer()
            # await self._change_stage(Stage.QUESTION)

        if new_stage == Stage.QUESTION:
            if self.question_index >= len(self.questions):
                await self._end_interactive_all()
                return
            self.timer_duration = self.answer_duration
            self.remaining_time = self.answer_duration
            self.time_task = asyncio.create_task(self.question_timer())

        if new_stage == Stage.DISCUSSION:
            self.timer_duration = self.discussion_duration
            self.remaining_time = self.discussion_duration
            self.time_task = asyncio.create_task(self.discussion_timer())

        if new_stage == Stage.END:
            await self._end_interactive_all()

    async def _end_interactive_all(self):
        self.stage = Stage.END
        if self.time_task is not None:
            self.time_task.cancel()
            try:
                await self.time_task
            except asyncio.CancelledError:
                pass
        self.time_task = None
        participants_total = await Repository.get_participant_count(self.interactive_id)
        winners = await Repository.get_winners(self.interactive_id)  # тут проблема
        data = DataStageEnd(title=self.title, participants_total=participants_total, winners=winners)
        await self.broadcast_callback(self.interactive_id, StageEnd(stage=self.stage, data=data).model_dump())
        # Помечаем интерактив как завершённый в БД
        await asyncio.sleep(1)
        await Repository.mark_interactive_conducted(self.interactive_id)

    async def countdonw_timer(self):
        try:
            while self.remaining_time >= 0:
                await self.broadcast_callback(self.interactive_id, StageCountdown(stage=self.stage, data=DataStageCountdown(
                    timer=self.remaining_time)).model_dump())
                await asyncio.sleep(1)
                self.remaining_time -= self.second_step
            await self._change_stage(Stage.QUESTION)
        except asyncio.CancelledError:
            return

    async def question_timer(self):
        try:
            while self.remaining_time >= 0:
                answer = await Repository.get_question_answers(self.current_question.id)
                data = DataStageQuestion(questions_count=len(self.questions), timer=self.remaining_time,
                                         timer_duration=self.timer_duration, title=self.title, code=self.code,
                                         question=self.current_question, answers=answer)
                result = StageQuestion(stage=self.stage, data=data)
                await self.broadcast_callback(self.interactive_id, result.model_dump())
                await asyncio.sleep(1)
                self.remaining_time -= self.second_step
            await self._change_stage(Stage.DISCUSSION)
        except asyncio.CancelledError:
            return

    async def discussion_timer(self):
        try:
            while self.remaining_time >= 0:
                percentages = await  Repository.get_percentages(self.current_question.id)
                id_correct_answer = await Repository.get_correct_answer(self.current_question.id)
                data = DataStageDiscussion(questions_count=len(self.questions), timer=self.remaining_time,
                                           timer_duration=self.timer_duration, title=self.title, code=self.code,
                                           question=self.current_question, id_correct_answer=id_correct_answer,
                                           percentages=percentages)
                result = StageDiscussion(stage=self.stage, data=data)
                await self.broadcast_callback(self.interactive_id, result.model_dump())
                await asyncio.sleep(1)
                self.remaining_time -= self.second_step

            await self._change_question()
            await self._change_stage(Stage.QUESTION)
        except asyncio.CancelledError:
            return

    async def waiting_timer(self):
        try:
            while self.waiting_timer_flag:
                await asyncio.sleep(1)
                participants_count = await  self.get_participants_count(self.interactive_id)
                data = DataStageWaiting(title=self.title, description=self.description, code=self.code,
                                        participants_active=participants_count)
                result = StageWaiting(stage=self.stage, data=data)
                await self.broadcast_callback(self.interactive_id, result.model_dump())
            await self._change_stage(Stage.COUNTDOWN)
        except asyncio.CancelledError:
            return
    #
    # async def _start_timer(self, duration: int):
    #     if self.timer_task and not self.timer_task.done():
    #         self.timer_task.cancel()
    #
    #     self.timer_duration = duration
    #     self.remaining_time = duration
    #     self.timer_start_time = asyncio.get_event_loop().time()
    #
    #     self.timer_task = asyncio.create_task(self._run_timer())
    #     # Добавляем обработку ошибок задачи
    #     self.timer_task.add_done_callback(self._handle_timer_task_done)
    #
    # async def _run_timer(self):
    #     start_time = asyncio.get_event_loop().time()
    #     end_time = start_time + self.timer_duration
    #
    #     while True:
    #         current_time = asyncio.get_event_loop().time()
    #         if current_time >= end_time or self._stop_event.is_set():
    #             break
    #
    #         self.remaining_time = max(0, end_time - current_time)
    #         await asyncio.sleep(0.1)  # Обновляем время 10 раз в секунду
    #
    #         # Рассылаем обновление таймера каждую секунду
    #         if int(self.remaining_time) != int(self.remaining_time + 0.1):
    #             await self._broadcast_state(only_timer=True)
    #
    #     if not self._stop_event.is_set():
    #         self.remaining_time = 0
    #
    # async def _wait_for_timer(self):
    #     try:
    #         while self.remaining_time > 0 and not self._stop_event.is_set():
    #             await asyncio.sleep(0.1)
    #     except asyncio.CancelledError:
    #         pass
    #
    # async def _broadcast_state(self, only_timer: bool = False):
    #     state = await self._get_current_state(only_timer)
    #     if state and self.broadcast_callback:
    #         await self.broadcast_callback(self.interactive_id, json.dumps(state))
    #
    # async def _get_current_state(self, only_timer: bool = False) -> dict:
    #     if self.stage == Stage.WAITING:
    #         if only_timer:
    #             return None
    #
    #         return {
    #             "stage": self.stage.value,
    #             "data": {
    #                 "title": self.title,
    #                 "description": self.description,
    #                 "code": self.code,
    #                 "participants_active": self.get_participants_count(self.interactive_id)
    #             }
    #         }
    #
    #     elif self.stage == Stage.COUNTDOWN:
    #         return {
    #             "stage": self.stage.value,
    #             "data": {
    #                 "timer": int(self.remaining_time)
    #             }
    #         }
    #
    #     elif self.stage == Stage.QUESTION and self.current_question:
    #         if only_timer:
    #             return {
    #                 "stage": self.stage.value,
    #                 "data": {
    #                     "timer": int(self.remaining_time)
    #                 }
    #             }
    #
    #         answers = await Repository.get_question_answers(self.current_question.id)
    #
    #         return {
    #             "stage": self.stage.value,
    #             "data": {
    #                 "timer": int(self.remaining_time),
    #                 "title": self.title,
    #                 "code": self.code,
    #                 "question": {
    #                     "id": self.current_question.id,
    #                     "text": self.current_question.text,
    #                     "position": self.current_question.position,
    #                 },
    #                 "answers": [{"id": a.id, "text": a.text} for a in answers]
    #             }
    #         }
    #
    #     elif self.stage == Stage.DISCUSSION and self.current_question:
    #         if only_timer:
    #             return {
    #                 "stage": self.stage.value,
    #                 "data": {
    #                     "timer": int(self.remaining_time)
    #                 }
    #             }
    #
    #         correct_answer = await Repository.get_correct_answer(self.current_question.id)
    #         percentages = await Repository.get_percentages(self.current_question.id)
    #
    #         return {
    #             "stage": self.stage.value,
    #             "data": {
    #                 "timer": int(self.remaining_time),
    #                 "title": self.title,
    #                 "code": self.code,
    #                 "question": {
    #                     "id": self.current_question.id,
    #                     "text": self.current_question.text,
    #                     "position": self.current_question.position,
    #                 },
    #                 "id_correct_answer": correct_answer,
    #                 "percentages": [{"id": p.id, "percentage": p.percentage} for p in percentages]
    #             }
    #         }
    #
    #     elif self.stage == Stage.END:
    #         if only_timer:
    #             return None
    #
    #         winners = await Repository.get_winners(self.interactive_id)
    #
    #         return {
    #             "stage": self.stage.value,
    #             "data": {
    #                 "title": self.title,
    #                 "participants_total": self.get_participants_count(self.interactive_id)
    #             },
    #             "winners": [{"position": i + 1, "username": w.username} for i, w in enumerate(winners)]
    #         }
    #
    #     return None
