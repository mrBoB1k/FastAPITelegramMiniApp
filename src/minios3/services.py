from minio import Minio
from minio.error import S3Error
import io
from fastapi import UploadFile, HTTPException
import os
from minios3.schemas import ImageModel
import transliterate
import re

# Конфигурация MinIO
minio_client = Minio(
    "minio:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)

async def save_image_to_minio(file: bytes, filename: str, unique_filename: str, content_type: str, size: int, bucket_name: str) -> ImageModel:
    # Создаем бакет если не существует
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"Error creating bucket: {exc}")

    if '.' in filename:
        name_part, extension_part = filename.rsplit('.', 1)
    else:
        name_part = filename
        extension_part = ""

    translit_title = smart_translit(name_part).lower().replace(' ', '_')
    translit_title = re.sub(r'[^\w_]', '', translit_title)

    # Загружаем в MinIO
    try:
        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=unique_filename,
            data=io.BytesIO(file),
            length=size,
            content_type=content_type,
            metadata={
                "original-filename": f"{translit_title}.{extension_part}"
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


async def get_image_from_minio(unique_filename: str, bucket_name: str) -> str:
    # Удаляем объекты из бакета MinIO
    try:
        file = minio_client.get_object(
            bucket_name=bucket_name,
            object_name=unique_filename
        )
        return file
    except S3Error as exc:
        return f"{exc}"


def smart_translit(text):
    words = re.findall(r'([а-яА-ЯёЁ]+|\w+|[^\w\s]+|\s+)', text)
    result = []

    for word in words:
        # Если слово содержит кириллицу — транслитерируем
        if re.search(r'[а-яА-ЯёЁ]', word):
            try:
                translit_word = transliterate.translit(word, 'ru', reversed=True)
                translit_word = translit_word.replace("'", "").replace('"', '')
                result.append(translit_word)
            except Exception as e:
                print(f"Transliteration error for '{word}': {e}")
                result.append(word)  # Если ошибка — оставляем как есть
        else:
            result.append(word)  # Английские слова и символы оставляем

    return ''.join(result)