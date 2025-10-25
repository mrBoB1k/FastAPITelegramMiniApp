from pydantic import BaseModel

class ImageModel(BaseModel):
    filename: str
    unique_filename: str
    content_type: str
    size: int
    bucket_name: str