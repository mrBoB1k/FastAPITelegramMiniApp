from pwdlib import PasswordHash
from config import SECRET_KEY, VK_APP_ID, VK_CLIENT_SECRET

# to get a string like this run:
# openssl rand -hex 32
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

REFRESH_COOKIE_NAME = "refresh_token"

password_hash_algorithm = PasswordHash.recommended()
DUMMY_HASH = password_hash_algorithm.hash("dummypassword")
