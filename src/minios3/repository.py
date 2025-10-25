from sqlalchemy import select, delete
from database import new_session
from models import *
from datetime import datetime
from minios3.schemas import *
import uuid

class Repository:
    @classmethod
    async def save_image_metadata(cls, data: ImageModel) -> int:
        async with new_session() as session:
            image_dict = data.model_dump()

            image = Image(**image_dict)
            session.add(image)

            await session.flush()
            await session.commit()
            return image.id

    @classmethod
    async def check_filename_exists(cls, unique_filename: str) -> bool:
        async with new_session() as session:
            result = await session.execute(
                select(Image.id).where(Image.unique_filename == unique_filename)
            )
            exists = result.scalar_one_or_none() is not None
            return exists

    @classmethod
    async def generate_unique_filename(cls, ext: str) -> str:
        while True:
            unique_filename = f"{uuid.uuid4()}.{ext}"
            if not await cls.check_filename_exists(unique_filename):
                return unique_filename