from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from typing import Annotated, Any, Type, Coroutine, List
from reports.schemas import TelegramId, PreviewInteractive, InteractiveList, ExportGet,ExportEnum
from reports.repository import Repository
from users.schemas import UserRoleEnum
from datetime import datetime
import io
import pandas as pd


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
        all_data = []
        for interactive_id_data in input_data.interactive_id:
            interactive_data = await Repository.get_interactive_export_for_analise(interactive_id_data.id)
            all_data.extend(interactive_data)

        df = pd.DataFrame([{
            "id_интерактива": item.interactive_id,
            "Название интерактива": item.title,
            "Дата проведения": item.date_completed,
            "Общее количество участников": item.participant_count,
            "Общее количество вопросов": item.question_count,
            "Целевая аудитория": item.target_audience,
            "Место проведения": item.location,
            "ФИО ведущего": item.responsible_full_name,
            "tg_id": item.telegram_id,
            "tg_username": item.username,
            "ФИО участника": item.full_name,
            "Количество правильных ответов": item.correct_answers_count
        } for item in all_data])

        # Создаем Excel файл в памяти
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Report', index=False)
            worksheet = writer.sheets['Report']

            # Автоподбор ширины колонок (опционально)
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_len)

        output.seek(0)

        headers = {
            'Content-Disposition': f'attachment; filename="analytics_report_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        return StreamingResponse(output, headers=headers)
    else:
        raise HTTPException(status_code=404, detail="Invalid export type") # позже будет второй тип отчёта
    # # Создаем Excel файл в памяти
    # output = io.BytesIO()
    # with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    #     df.to_excel(writer, sheet_name='Report', index=False)
    #
    # # Перемещаем указатель в начало файла
    # output.seek(0)
    #
    # # Возвращаем файл как поток
    # headers = {
    #     'Content-Disposition': 'attachment; filename="report.xlsx"',
    #     'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    # }
    # return StreamingResponse(output, headers=headers)

