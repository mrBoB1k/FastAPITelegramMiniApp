from config import SECRET_KEY
from exceptions import XKeyInvalidException

async def verify_key(x_key: str):
    if x_key != SECRET_KEY:
        raise XKeyInvalidException()
    return x_key