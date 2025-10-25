from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Annotated
import minios3.services as services
from minios3.schemas import ImageModel
from minios3.repository import Repository

router = APIRouter(
    prefix="/api/test",
    tags=["/api/test"]
)

MAX_FILE_SIZE = 5 * 1024 * 1024

@router.post("/upload2")
async def create_file(
    image: UploadFile,
):
    # Проверка размера
    file_size = image.size
    content_type = image.content_type

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 5 MB limit"
        )

    # Проверка, что это изображение
    if not content_type or not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {content_type}. Only images are allowed."
        )

    # Определяем расширение из MIME-типа
    mime_to_ext = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
        "image/svg+xml": "svg"
    }
    ext = mime_to_ext.get(content_type, "bin")

    # Генерируем уникальное имя файла
    unique_filename = await Repository.generate_unique_filename(ext)
    filename = image.filename

    # Сохраняем в MinIO
    image_data = await services.save_image_to_minio(
        file=await image.read(),
        filename=filename,
        unique_filename=unique_filename,
        content_type=content_type,
        size=file_size,
    )

    id = await Repository.save_image_metadata(image_data)

    return {"id":id,"unique_filename":unique_filename, "filename":filename}