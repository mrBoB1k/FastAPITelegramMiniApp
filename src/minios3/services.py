from minio import Minio
from minio.error import S3Error
import io
from fastapi import UploadFile, HTTPException
import os
from minios3.schemas import ImageModel

# Конфигурация MinIO
minio_client = Minio(
    "minio:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)

async def save_image_to_minio(file: bytes, filename: str, unique_filename: str, content_type: str, size: int) -> ImageModel:
    bucket_name = "images"

    # Создаем бакет если не существует
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"Error creating bucket: {exc}")

    # Загружаем в MinIO
    try:
        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=unique_filename,
            data=io.BytesIO(file),
            length=size,
            content_type=content_type,
            metadata={
                "original-filename": filename
            }
        )
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {exc}")

    return ImageModel(filename=filename, unique_filename=unique_filename, content_type=content_type,size=size, bucket_name=bucket_name)


async def delete_image_from_minio(unique_filename: str, bucket_name: str) -> str:
    # Удаляем объекты из бакета MinIO
    try:
        minio_client.remove_object(
            bucket_name=bucket_name,
            object_name=unique_filename
        )
        return "True"
    except S3Error as exc:
        return f"{exc}"
