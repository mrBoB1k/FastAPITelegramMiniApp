from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
import uuid
import minios3.services as services

router = APIRouter(
    prefix="/api/test",
    tags=["/api/test"]
)


@router.post("/upload")
async def upload_image(
    file: UploadFile,
):
    # Генерируем уникальное имя файла
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
    unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())

    # Сохраняем файл в MinIO
    image_data = await services.save_image_to_minio(
        file=file,
        filename=unique_filename
    )

    return unique_filename