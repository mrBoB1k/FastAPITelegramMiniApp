from pydantic import BaseModel

class Image(BaseModel):
    filename: str
    content_type: str
    size: int
    bucket_name: str