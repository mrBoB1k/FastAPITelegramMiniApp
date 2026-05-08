from datetime import datetime, timedelta, timezone
import jwt
import uuid
import json
import base64
from collections import OrderedDict
from hmac import HMAC
from urllib.parse import urlencode, unquote
import time
import hashlib

from auth.auth_config import SECRET_KEY, ALGORITHM, password_hash_algorithm, DUMMY_HASH, ACCESS_TOKEN_EXPIRE_MINUTES
from auth.repository import Repository
from auth.schemas import TokenData, AuthenticateUserSchema, RefreshTokenSchema, TokenRegisterData


def verify_password(plain_password, password_hash):
    return password_hash_algorithm.verify(plain_password, password_hash)


def get_password_hash(password):
    return password_hash_algorithm.hash(password)


async def authenticate_user(login: str, password: str) -> AuthenticateUserSchema | None:
    user = await Repository.get_user(login)

    if not user:
        verify_password(password, DUMMY_HASH)
        return None

    participant = await Repository.get_participant(user.id)
    if not participant:
        return None

    if not verify_password(password, user.password_hash):
        return None

    data = AuthenticateUserSchema(id=user.id, login=user.login, email=user.email,
                                  participant_id=participant.participant_id,
                                  organization_id=participant.organization_id, role=participant.role)
    return data


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_datetime_expire(expires_delta: timedelta):
    expire = datetime.now(timezone.utc) + expires_delta
    return expire


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as e:
        print(e)
        return None
    participant_id = payload.get("participant_id")
    organization_id = payload.get("organization_id")
    role = payload.get("role")
    token_id = payload.get("token_id")
    token_version = payload.get("token_version")

    if participant_id is None:
        return None

    return TokenData(participant_id=participant_id,
                     organization_id=organization_id,
                     role=role,
                     token_id=token_id,
                     token_version=token_version
                     )

def decode_token_for_register(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as e:
        print(e)
        return None
    email = payload.get("email")
    organization_id = payload.get("organization_id")
    role = payload.get("role")

    if email is None:
        return None

    return TokenRegisterData(
        email=email,
        organization_id=int(organization_id),
        role=role,
    )

def decode_token_for_reset(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as e:
        print(e)
        return None
    user_id = payload.get("user_id")

    if user_id is None:
        return None

    return int(user_id)

def decode_token_for_participant(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as e:
        print(e)
        return None
    user_id = payload.get("user_id")

    return user_id


def decode_base64(data: str) -> dict:
    decoded_bytes = base64.b64decode(data)
    decoded_str = decoded_bytes.decode('utf-8')
    result_dict = json.loads(decoded_str)
    return {str(k): str(v) for k, v in result_dict.items()}


def is_valid_vk_token(*, query: dict, secret: str) -> bool:
    """Check s Apps signature"""
    vk_subset = OrderedDict(
        sorted(x for x in query.items() if x[0][:3] == "vk_")
    )
    hash_code = base64.b64encode(
        HMAC(secret.encode(), urlencode(vk_subset, doseq=True).encode(), hashlib.sha256).digest()
    )

    decoded_hash_code = hash_code.decode('utf-8')[:-1].replace('+', '-').replace('/', '_')
    return query["sign"] == decoded_hash_code


def is_valid_vk_ts(vk_ts: str, max_age_seconds: int = 3600) -> bool:
    try:
        ts = int(vk_ts)
    except (ValueError, TypeError):
        return False

    now = int(time.time())
    return now - ts <= max_age_seconds


def generate_vk_sign(
        *,
        app_id: int | str,
        api_secret: str,
        vk_user_id: int | str,
        field_name: str,
        field_value: str,
) -> str:
    raw_string = f"{app_id}{api_secret}{vk_user_id}{field_name}{field_value}"
    digest = hashlib.sha256(raw_string.encode("utf-8")).digest()
    b64 = base64.b64encode(digest).decode("utf-8")
    sign = b64.rstrip("=").replace("+", "-").replace("/", "_")

    return sign


async def create_refresh_token(user_id: int, refresh_token_expires: datetime) -> RefreshTokenSchema | None:
    token = str(uuid.uuid4())

    token_hash = get_password_hash(token)

    token_data = await Repository.create_session(user_id=user_id, token_hash=token_hash,
                                                 expires_at=refresh_token_expires)
    if token_data is None:
        return None

    token_id = token_data.id

    return RefreshTokenSchema(token_id=token_id, token=token)


async def check_refresh_token(token_data: RefreshTokenSchema) -> AuthenticateUserSchema | None:
    session_data = await Repository.get_valid_session(token_data.token_id)

    if session_data is None:
        verify_password(token_data.token, DUMMY_HASH)
        return None

    user_data = await Repository.get_user_by_id(session_data.user_id)
    if not user_data:
        return None

    participant = await Repository.get_participant(user_data.id)
    if not participant:
        return None

    if not verify_password(token_data.token, session_data.token_hash):
        return None

    data = AuthenticateUserSchema(id=user_data.id, login=user_data.login, email=user_data.email,
                                  participant_id=participant.participant_id,
                                  organization_id=participant.organization_id, role=participant.role)
    return data
