from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Annotated
from reports.schemas import TelegramId, InteractiveList, ExportGet, ExportEnum
from reports.repository import Repository
import io
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.writer.excel import save_virtual_workbook
import transliterate
import re

router = APIRouter(
    prefix="/api/reports",
    tags=["/api/reports"]
)


@router.get("/preview")
async def get_preview(telegram_id: Annotated[TelegramId, Depends()]) -> InteractiveList:
    user_id = await Repository.get_user_id(telegram_id.telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = await Repository.get_reports_preview(user_id)
    return data


@router.post("/export")
async def get_export(input_data: ExportGet) -> StreamingResponse:
    user_id = await Repository.get_user_id(input_data.telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    if input_data.report_type == ExportEnum.forAnalise.value:
        wb = Workbook()
        ws = wb.active
        ws.title = "Analytics Report"

        # Заголовки
        headers = [
            "id_интерактива", "Название интерактива", "Дата проведения",
            "Общее количество участников", "Общее количество вопросов",
            "Целевая аудитория", "Место проведения", "ФИО ведущего",
            "tg_id", "tg_username", "ФИО участника", "Количество правильных ответов"
        ]
        ws.append(headers)

        # Данные
        for interactive_id_data in input_data.interactive_id:
            items = await Repository.get_interactive_export_for_analise(interactive_id_data.id)
            for item in items:
                ws.append([
                    item.interactive_id,
                    item.title,
                    item.date_completed,
                    item.participant_count,
                    item.question_count,
                    item.target_audience,
                    item.location,
                    item.responsible_full_name,
                    item.telegram_id,
                    item.username,
                    item.full_name,
                    item.correct_answers_count
                ])

        # Возвращаем файл
        filename = "analytics_report.xlsx"
        if len(input_data.interactive_id) == 1:
            data_title_date = await Repository.get_title_and_date_for_interactive(input_data.interactive_id[0].id)
            if data_title_date:
                translit_title =  smart_translit(data_title_date.title).lower().replace(' ', '_')
                translit_title = re.sub(r'[^\w_]', '', translit_title)
                filename = f"{translit_title}_{data_title_date.date_completed}.xlsx"

        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        return StreamingResponse(
            io.BytesIO(save_virtual_workbook(wb)),
            headers=headers
        )

    elif input_data.report_type == ExportEnum.forLeader.value:
        wb = Workbook()
        wb.remove(wb.active)  # Удаляем дефолтный лист

        for interactive_id_data in input_data.interactive_id:
            data = await Repository.get_export_for_leader(interactive_id_data.id)

            # Создаем новый лист для каждого интерактива
            ws = wb.create_sheet(title=f"Интерактив {data.header.interactive_id}")

            # Настройка ширины столбцов
            for col in range(1, 14):
                ws.column_dimensions[get_column_letter(col)].width = 15

            # Стили
            correct_answer_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
            bold_font = Font(bold=True)
            center_alignment = Alignment(horizontal='center')

            # 1. Заголовок интерактива (A1:M7)
            interact_info = [
                f"Название интерактива: {data.header.title}",
                f"Id_интерактива: {data.header.interactive_id}",
                f"Дата проведения: {data.header.date_completed}",
                f"Общее количество участников: {len(data.body)}",
                f"Целевая аудитория: {data.header.target_audience}" if data.header.target_audience else "Целевая аудитория: не указано",
                f"Место проведения: {data.header.location}" if data.header.location else "Место проведения: не указано",
                f"ФИО ведущего: {data.header.responsible_full_name}" if data.header.responsible_full_name else "ФИО ведущего: не указано"
            ]

            for i, info in enumerate(interact_info, start=1):
                cell = ws.cell(row=i, column=1, value=info)
                ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=13)
                cell.font = bold_font

            # 2. Вопросы и ответы (строка 11-14)
            current_col = 6  # Начинаем с колонки F

            for question in sorted(data.header.question, key=lambda q: q.position):
                answer_count = len(question.answers)

                # Заголовок вопроса (строка 11)
                ws.cell(row=11, column=current_col, value=f"Вопрос {question.position}").font = bold_font
                ws.merge_cells(start_row=11, start_column=current_col, end_row=11,
                               end_column=current_col + answer_count - 1)

                # Текст вопроса (строка 12)
                ws.cell(row=12, column=current_col, value=question.text)
                ws.merge_cells(start_row=12, start_column=current_col, end_row=12,
                               end_column=current_col + answer_count - 1)

                # Варианты ответов (строка 13)
                for i in range(answer_count):
                    ws.cell(row=13, column=current_col + i, value=f"Ответ {i + 1}")

                # Тексты ответов (строка 14)
                for i, answer in enumerate(question.answers):
                    cell = ws.cell(row=14, column=current_col + i, value=answer.text)
                    if answer.is_correct:
                        cell.fill = correct_answer_fill

                current_col += answer_count  # Сдвигаем на нужное количество колонок

            # 3. Заголовки таблицы участников (строка 15)
            headers = ["№", "telegram_id", "username", "ФИО", "Правильных ответов"]
            for col, header in enumerate(headers, start=1):
                ws.cell(row=15, column=col, value=header).font = bold_font

            # 4. Данные участников (начиная со строки 16)
            for i, participant in enumerate(data.body, start=1):
                row = 15 + i

                # Основная информация
                ws.cell(row=row, column=1, value=i).alignment = center_alignment
                ws.cell(row=row, column=2, value=participant.telegram_id)
                ws.cell(row=row, column=3, value=participant.username)
                ws.cell(row=row, column=4, value=participant.full_name)
                ws.cell(row=row, column=5, value=f"{participant.correct_answers_count}/{len(data.header.question)}")

                # Ответы участника
                current_col = 6
                for question in sorted(data.header.question, key=lambda q: q.position):
                    answer_count = len(question.answers)

                    # Сначала заполняем все 0
                    for j in range(answer_count):
                        ws.cell(row=row, column=current_col + j, value=0).alignment = center_alignment

                    # Затем отмечаем выбранные ответы
                    for answer in participant.answers:
                        if answer.question_id == question.id:
                            for j, a in enumerate(question.answers):
                                if a.id == answer.answer_id:
                                    ws.cell(row=row, column=current_col + j, value=1).alignment = center_alignment

                    current_col += answer_count

            # 5. Подсчет ответивших (строка после последнего участника)
            stats_row = 15 + len(data.body) + 1
            ws.cell(row=stats_row, column=5, value="Количество ответивших").font = bold_font

            current_col = 6
            for question in sorted(data.header.question, key=lambda q: q.position):
                answer_count = len(question.answers)

                for j in range(answer_count):
                    col = current_col + j
                    first_row = 16
                    last_row = 15 + len(data.body)
                    ws.cell(row=stats_row, column=col,
                            value=f"=SUM({get_column_letter(col)}{first_row}:{get_column_letter(col)}{last_row})")

                current_col += answer_count

        # Возвращаем файл как поток
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = "leader_report.xlsx"
        if len(input_data.interactive_id) == 1:
            data_title_date = await Repository.get_title_and_date_for_interactive(input_data.interactive_id[0].id)
            if data_title_date:
                translit_title =  smart_translit(data_title_date.title).lower().replace(' ', '_')
                translit_title = re.sub(r'[^\w_]', '', translit_title)
                filename = f"{translit_title}_{data_title_date.date_completed}.xlsx"

        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        return StreamingResponse(output, headers=headers)

    else:
        raise HTTPException(status_code=400, detail="Invalid export type")


def smart_translit(text):
    # Разделяем текст на слова и символы
    words = re.findall(r'([а-яА-ЯёЁ]+|\w+|[^\w\s]+|\s+)', text)
    result = []

    for word in words:
        # Если слово содержит кириллицу — транслитерируем
        if re.search(r'[а-яА-ЯёЁ]', word):
            try:
                # Указываем язык явно (русский) и включаем строгий режим
                translit_word = transliterate.translit(word, 'ru', reversed=True)
                # Заменяем мягкий/твёрдый знаки на апостроф или удаляем
                translit_word = translit_word.replace("'", "").replace('"', '')
                result.append(translit_word)
            except Exception as e:
                print(f"Transliteration error for '{word}': {e}")
                result.append(word)  # Если ошибка — оставляем как есть
        else:
            result.append(word)  # Английские слова и символы оставляем

    return ''.join(result)