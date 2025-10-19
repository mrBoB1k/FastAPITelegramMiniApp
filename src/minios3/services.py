from minio import Minio
from minio.error import S3Error
import io
from fastapi import UploadFile, HTTPException
import os
from minios3.schemas import Image

# Конфигурация MinIO
minio_client = Minio(
    "minio:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)


async def save_image_to_minio(file: UploadFile, filename: str) -> Image:
    bucket_name = "images"

    # Создаем бакет если не существует
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"Error creating bucket: {exc}")

    # Читаем файл
    contents = await file.read()
    file_size = len(contents)

    # Загружаем в MinIO
    try:
        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=filename,
            data=io.BytesIO(contents),
            length=file_size,
            content_type=file.content_type
        )
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {exc}")

    return Image(filename=filename, content_type=file.content_type,size=file_size, bucket_name=bucket_name)
