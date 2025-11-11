from typing import List, Callable, Any, Coroutine
import asyncio
from enum import Enum
from websocket.schemas import InteractiveInfo, InteractiveStatus, Question, StageCountdown, DataStageCountdown, \
    DataStageQuestion, StageQuestion, DataStageDiscussion, StageDiscussion, DataStageEnd, StageEnd, DataStageWaiting, \
    StageWaiting, AnswerGet, Answer, InteractiveStatus, StatePause, DataPause, QuestionType
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
        self.current_question: Question | None = None # для простаты запоминаю текущий вопрос
        self.current_answers: list[AnswerGet] | None = None # оптимизация получения вопросов

        self.get_participants_count = get_participants_count  # callback для получения кол-во активных пользователей
        self.broadcast_callback = broadcast_callback  # callback для отправки сообщения
        self._manager_ref = weakref.ref(session_manager)

        self.timer_n = 30 * 60
        self.state = StatePause.yes

        self.timer_for_rating = 0  # для подсчёта кол-во секунд которые затратили участники

    async def get_stage(self) -> Stage:
        """Получение текущей фазы"""
        return self.stage

    async def get_question_data(self) -> Question | None:
        """Получение текущего вопроса"""
        return self.current_question

    async def get_answers_data(self):
        """Получение ответов на текущий вопрос"""
        return self.current_answers

    async def get_timer_passed(self):
        return self.timer_for_rating

    async def change_status(self, interactive_status: InteractiveStatus):
        """Обработка действий ведущего"""
        if interactive_status == InteractiveStatus.pause:
            if self.stage == Stage.WAITING or self.stage == Stage.END:
                return

            if self.second_step == 1:
                self.second_step = 0
                self.timer_n = 10 * 60
                self.state = StatePause.yes
            else:
                self.second_step = 1
                self.timer_n = 0
                self.state = StatePause.no


        elif interactive_status == InteractiveStatus.going:
            if self.stage != Stage.WAITING or self.stage == Stage.END:
                return
            self.waiting_timer_flag = False
            self.timer_n = 0
            self.state = StatePause.no
            return

        elif interactive_status == InteractiveStatus.end:
            if self.stage == Stage.END:
                return
            self.stage = Stage.END

        elif interactive_status == InteractiveStatus.more_pause:
            if self.stage == Stage.WAITING:
                self.timer_n = 30 * 60
                self.state = StatePause.yes

            elif (self.stage == Stage.QUESTION or self.stage == Stage.DISCUSSION) and self.second_step == 0:
                self.timer_n = 10 * 60
                self.state = StatePause.yes

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
            manager = self._manager_ref()
            if manager is not None:
                asyncio.create_task(manager.remove_session(self.interactive_id))

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
                    self.timer_for_rating = 0
                    return
            elif new_stage == Stage.DISCUSSION:
                await asyncio.sleep(1)
                await Repository.add_time_for_question(interactive_id=self.interactive_id,question_id=self.current_question.id,time_question=self.timer_for_rating)
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

            self.timer_n -= 1
            if self.timer_n <= 0:
                if self.state == StatePause.yes:
                    self.timer_n = 15 * 60
                    self.state = StatePause.timer_n
                elif self.state == StatePause.timer_n:
                    manager = self._manager_ref()
                    if manager is not None:
                        asyncio.create_task(manager.disconnect_delete(self.interactive_id))

            pause = DataPause(state=self.state, timer_n=self.timer_n)

            result = StageWaiting(stage=stage_now, pause=pause, data=data)
            await self.broadcast_callback(self.interactive_id, result, stage_now)
        await self._change_stage(Stage.COUNTDOWN)
        return

    async def _countdonw_timer(self):
        """цикл для фазы обратного отчёта"""
        while self.remaining_time >= 0 and self.stage != Stage.END:
            stage_now = self.stage
            await self.broadcast_callback(self.interactive_id, StageCountdown(stage=stage_now, data=DataStageCountdown(
                timer=self.remaining_time)), stage_now)
            await asyncio.sleep(1)
            self.remaining_time -= self.second_step
        await self._change_stage(Stage.QUESTION)
        return

    async def _question_timer(self):
        """цикл для фазы вопроса"""
        while self.remaining_time >= 0 and self.stage != Stage.END:
            stage_now = self.stage
            question_type = self.current_question.type

            answer = None
            if question_type == QuestionType.one or question_type == QuestionType.many:
                answer = [Answer(**ans.dict(include={'id', 'text'})) for ans in self.current_answers]

            data = DataStageQuestion(questions_count=len(self.questions), timer=self.remaining_time,
                                     timer_duration=self.timer_duration, title=self.title, code=self.code,
                                     question=self.current_question)

            if self.second_step == 0:
                self.timer_n -= 1
                if self.timer_n <= 0:
                    if self.state == StatePause.yes:
                        self.timer_n = 5 * 60
                        self.state = StatePause.timer_n
            pause = DataPause(state=self.state, timer_n=self.timer_n)

            result = StageQuestion(stage=stage_now, pause=pause, data=data, data_answers=answer)
            await self.broadcast_callback(self.interactive_id, result, stage_now)
            await asyncio.sleep(1)
            self.remaining_time -= self.second_step
            self.timer_for_rating += 1

            if self.second_step == 0 and self.timer_n <= 0 and self.state == StatePause.timer_n:
                self.stage = Stage.END

        await self._change_stage(Stage.DISCUSSION)
        return

    async def _discussion_timer(self):
        """цикл для фазы обсуждения"""
        while self.remaining_time >= 0 and self.stage != Stage.END:
            stage_now = self.stage
            question_type = self.current_question.type
            winners =  await Repository.get_winners_discussion(self.interactive_id)
            data = DataStageDiscussion(questions_count=len(self.questions), timer=self.remaining_time,
                                       timer_duration=self.timer_duration, title=self.title, code=self.code,
                                       question=self.current_question)
            if self.second_step == 0:
                self.timer_n -= 1
                if self.timer_n <= 0:
                    if self.state == StatePause.yes:
                        self.timer_n = 5 * 60
                        self.state = StatePause.timer_n
            pause = DataPause(state=self.state, timer_n=self.timer_n)
            result = StageDiscussion(stage=stage_now, pause=pause, data=data, data_answers=None,  winners=winners)
            await self.broadcast_callback(self.interactive_id, result, stage_now, question_type=question_type)
            await asyncio.sleep(1)
            self.remaining_time -= self.second_step

            if self.second_step == 0 and self.timer_n <= 0 and self.state == StatePause.timer_n:
                self.stage = Stage.END

        await self._change_stage(Stage.QUESTION)
        return

    async def _end_interactive(self):
        """Обработка завершения интерактива"""
        stage_now = self.stage
        participants_total = await Repository.get_participant_count(self.interactive_id)
        data = DataStageEnd(title=self.title, participants_total=participants_total)
        await self.broadcast_callback(self.interactive_id, StageEnd(stage=stage_now, data=data), stage_now)
        # Помечаем интерактив как завершённый в БД
        await Repository.mark_interactive_conducted(self.interactive_id)
