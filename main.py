from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    telegram_id: int
    username: str
    first_name: str
    last_name: str = None
    phone_number: str  = None

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    user = User(telegram_id=123, username=name, first_name=name)
    return {"message": user}
