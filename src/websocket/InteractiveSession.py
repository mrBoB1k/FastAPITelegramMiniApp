from typing import List, Callable, Any
import asyncio
from enum import Enum
from websocket.schemas import InteractiveInfo, InteractiveStatus, Question, StageCountdown, DataStageCountdown, \
    DataStageQuestion, StageQuestion, DataStageDiscussion, StageDiscussion, DataStageEnd, StageEnd, DataStageWaiting, \
    StageWaiting, AnswerGet, Answer
from websocket.repository import Repository
import weakref


class Stage(str, Enum):
    WAITING = "waiting"
    COUNTDOWN = "countdown"
    QUESTION = "question"
    DISCUSSION = "discussion"
    END = "end"


class InteractiveSession:
    def __init__(self, meta_data: InteractiveInfo, questions: List[Question],
                 broadcast_callback: Callable[[int, str], Any],
                 get_participants_count: Callable[[int], Any],
                 session_manager):
        self.interactive_id: int = meta_data.interactive_id  # из бд
        self.code: str = meta_data.code  # из бд
        self.title: str = meta_data.title  # из бд
        self.description: str = meta_data.description  # из бд
        self.answer_duration: int = meta_data.answer_duration  # из бд
        self.discussion_duration: int = meta_data.discussion_duration  # из бд
        self.countdown_duration: int = meta_data.countdown_duration  # из бд

        self.stage: Stage = Stage.WAITING  # фаза, нужна для обработки логики

        self.time_task: asyncio.Task | None = None  # цикл интерактива
        self.timer_duration: int = 0  # таймер изначально, на текущей фазе
        self.remaining_time: int = 0  # оставшееся время, на текущей фазе

        self.waiting_timer_flag: bool = True  # обработка фазы waiting
        self.second_step: int = 1  # для постановки интерактива на паузу

        self.question_index: int = -1  # индекс текущий вопрос
        self.questions: List[Question] = questions  # сохраняю в оперативу сразу все вопросы
        self.current_question: Question | None  # для простаты запоминаю текущий вопрос
        self.current_answers: AnswerGet | None  # оптимизация получения вопросов

        self.get_participants_count = get_participants_count  # callback для получения кол-во активных пользователей
        self.broadcast_callback = broadcast_callback  # callback для отправки сообщения
        self._manager_ref = weakref.ref(session_manager)

    async def get_stage(self) -> Stage:
        """Получение текущей фазы"""
        return self.stage

    async def get_question_id(self) -> int:
        """Получение id текущего вопроса"""
        if self.current_question:
            return self.current_question.id
        return -1

    async def get_id_answers(self) -> list[int]:
        if self.current_answers is not None:
            return [ans.id for ans in self.current_answers]
        return []

    async def change_status(self, interactive_status: InteractiveStatus):
        """Обработка действий ведущего"""
        if interactive_status == InteractiveStatus.pause:
            if self.stage == Stage.WAITING or self.stage == Stage.END:
                return

            if self.second_step == 1:
                self.second_step = 0
            else:
                self.second_step = 1

        elif interactive_status == InteractiveStatus.going:
            if self.stage != Stage.WAITING or self.stage == Stage.END:
                return
            self.waiting_timer_flag = False
            return

        elif interactive_status == InteractiveStatus.end:
            if self.stage == Stage.END:
                return
            self.stage = Stage.END

        return

    async def start(self):
        self.time_task = asyncio.create_task(self._main_loop())
        self.time_task.add_done_callback(self._task_done)

    async def stop(self):
        if self.time_task is not None:
            self.time_task.cancel()  # Отправляем запрос на отмену задачи
            try:
                await self.time_task  # Ждём завершения задачи (нужно для обработки исключения отмены)
            except asyncio.CancelledError:
                pass  # Ожидаемое исключение при отмене задачи
            self.time_task = None

    def _task_done(self, task):
        manager = self._manager_ref()
        if manager is not None:
            asyncio.create_task(manager.remove_session(self.interactive_id))

    async def _change_stage(self, new_stage: Stage):
        """Смена фазы интерактива"""
        if self.stage != Stage.END:
            if new_stage == Stage.QUESTION:
                if self.question_index >= len(self.questions) - 1:
                    self.stage = Stage.END
                    return
                else:
                    self.question_index += 1
                    self.current_question = self.questions[self.question_index]
                    self.current_answers = await Repository.get_question_answers(self.current_question.id)
                    self.stage = new_stage
                    return
            else:
                self.stage = new_stage
                return
        return

    async def _main_loop(self):
        """Основной цикл программы"""
        try:
            while self.stage != Stage.END:
                if self.stage == Stage.WAITING:
                    await self._waiting_timer()

                elif self.stage == Stage.COUNTDOWN:
                    self.timer_duration = self.countdown_duration
                    self.remaining_time = self.countdown_duration
                    await self._countdonw_timer()

                elif self.stage == Stage.QUESTION:
                    self.timer_duration = self.answer_duration
                    self.remaining_time = self.answer_duration
                    await self._question_timer()

                elif self.stage == Stage.DISCUSSION:
                    self.timer_duration = self.discussion_duration
                    self.remaining_time = self.discussion_duration
                    await self._discussion_timer()
            await self._end_interactive()
        finally:
            pass

    async def _waiting_timer(self):
        """Цикл для фазы ожидания"""
        while self.waiting_timer_flag and self.stage != Stage.END:
            stage_now = self.stage
            await asyncio.sleep(1)
            participants_count = await  self.get_participants_count(self.interactive_id)
            data = DataStageWaiting(title=self.title, description=self.description, code=self.code,
                                    participants_active=participants_count)
            result = StageWaiting(stage=stage_now, data=data)
            await self.broadcast_callback(self.interactive_id, result.model_dump())
        await self._change_stage(Stage.COUNTDOWN)
        return

    async def _countdonw_timer(self):
        """цикл для фазы обратного отчёта"""
        while self.remaining_time >= 0 and self.stage != Stage.END:
            stage_now = self.stage
            await self.broadcast_callback(self.interactive_id, StageCountdown(stage=stage_now, data=DataStageCountdown(
                timer=self.remaining_time)).model_dump())
            await asyncio.sleep(1)
            self.remaining_time -= self.second_step
        await self._change_stage(Stage.QUESTION)
        return

    async def _question_timer(self):
        """цикл для фазы вопроса"""
        while self.remaining_time >= 0 and self.stage != Stage.END:
            stage_now = self.stage
            answer = [Answer(**ans.dict(include={'id', 'text'})) for ans in self.current_answers]
            data = DataStageQuestion(questions_count=len(self.questions), timer=self.remaining_time,
                                     timer_duration=self.timer_duration, title=self.title, code=self.code,
                                     question=self.current_question, answers=answer)
            result = StageQuestion(stage=stage_now, data=data)
            await self.broadcast_callback(self.interactive_id, result.model_dump())
            await asyncio.sleep(1)
            self.remaining_time -= self.second_step
        await self._change_stage(Stage.DISCUSSION)
        return

    async def _discussion_timer(self):
        """цикл для фазы обсуждения"""
        while self.remaining_time >= 0 and self.stage != Stage.END:
            stage_now = self.stage
            percentages = await  Repository.get_percentages(self.current_question.id)
            id_correct_answer = next((ans.id for ans in self.current_answers if ans.is_correct), -1)
            data = DataStageDiscussion(questions_count=len(self.questions), timer=self.remaining_time,
                                       timer_duration=self.timer_duration, title=self.title, code=self.code,
                                       question=self.current_question, id_correct_answer=id_correct_answer,
                                       percentages=percentages)
            result = StageDiscussion(stage=stage_now, data=data)
            await self.broadcast_callback(self.interactive_id, result.model_dump())
            await asyncio.sleep(1)
            self.remaining_time -= self.second_step

        await self._change_stage(Stage.QUESTION)
        return

    async def _end_interactive(self):
        """Обработка завершения интерактива"""
        participants_total = await Repository.get_participant_count(self.interactive_id)
        winners = await Repository.get_winners(self.interactive_id)  # тут проблема
        data = DataStageEnd(title=self.title, participants_total=participants_total, winners=winners)
        await self.broadcast_callback(self.interactive_id, StageEnd(stage=self.stage, data=data).model_dump())
        # Помечаем интерактив как завершённый в БД
        await Repository.mark_interactive_conducted(self.interactive_id)
