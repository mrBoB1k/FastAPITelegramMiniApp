# from minio import Minio
# from minio.error import S3Error
import io
from fastapi import UploadFile, HTTPException
import os
from minios3.schemas import ImageModel

import boto3
from botocore.exceptions import ClientError

session = boto3.session.Session()
s3 = session.client(
    service_name='s3',
    endpoint_url=os.environ["BOTO3_ENDPOINT_URL"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)


async def save_image_to_minio(file: bytes, filename: str, unique_filename: str, content_type: str, size: int, bucket_name: str) -> ImageModel:
    # Создаем бакет если не существует
    if not await check_and_create_bucket(bucket_name):
        raise HTTPException(status_code=500, detail=f"Error creating bucket")

    # Загружаем в MinIO
    try:
        # Создаем BytesIO объект из байтов
        file_stream = io.BytesIO(file)

        # Загружаем в S3
        s3.upload_fileobj(
            Fileobj=file_stream,
            Bucket=bucket_name,
            Key=unique_filename,
            ExtraArgs={
                'ContentType': content_type,
                'Metadata': {
                    'original-filename': filename
                }
            }
        )


    except ClientError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file to S3: {exc.response['Error']['Message']}"
        )

    return ImageModel(filename=filename, unique_filename=unique_filename, content_type=content_type,size=size, bucket_name=bucket_name)


async def delete_image_from_minio(unique_filename: str, bucket_name: str) -> str:
    # Удаляем объекты из бакета MinIO
    try:
        s3.delete_object(
            Bucket=bucket_name,
            Key=unique_filename
        )
        return "True"
    except ClientError as exc:
        error_message = exc.response['Error']['Message']
        return f"Error deleting file from S3: {error_message}"

async def check_and_create_bucket(bucket_name: str):
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Бакет '{bucket_name}' уже существует")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            # Бакет не существует, создаем
            try:
                s3.create_bucket(Bucket=bucket_name)
                print(f"Бакет '{bucket_name}' создан")
                return True
            except ClientError as create_error:
                print(f"Ошибка создания бакета: {create_error}")
                return False
        elif error_code == '403':
            print(f"Нет доступа к бакету '{bucket_name}'")
            return False
        else:
            print(f"Ошибка при проверке бакета: {e}")
            return False


async def get_presigned_url(unique_filename: str, bucket_name: str, expires_in: int = 3600) -> str:
    """
    Генерирует предварительно подписанный URL для доступа к файлу
    """
    try:
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket_name,
                'Key': unique_filename
            },
            ExpiresIn=expires_in  # Время жизни ссылки в секундах
        )
        return url
    except ClientError as exc:
        error_message = exc.response['Error']['Message']
        raise HTTPException(
            status_code=500,
            detail=f"Error generating URL: {error_message}"
        )