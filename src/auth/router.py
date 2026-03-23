from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response, Request, WebSocket
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from namer import generate
import string
import secrets

from models import UserRoleEnum
from exceptions import CredentialsException, InactiveUserException, IncorrectUserDataException, \
    InvalidRefreshTokenException, MissingRefreshTokenException, CredentialsWSException, InactiveUserWSException, \
    LeaderCannotAddNewUserException, CannotAddUserAnotherOrganizationException, InvalidEmailException, \
    EmailSendException
from organizations.schemas import NameInOrganization
from send_email import send_email, validate_receiver_email
from organizations.repository import Repository as Repository_Organization

from auth.repository import Repository
from auth.schemas import Token, RefreshTokenSchema, TokenData, AddOrganizationParticipantsEnum
from auth.untils import authenticate_user, create_access_token, create_refresh_token, decode_token, get_datetime_expire, \
    check_refresh_token, get_password_hash
from auth.auth_config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_COOKIE_NAME, REFRESH_TOKEN_EXPIRE_DAYS
from auth.redis_dict import redis_dict

router = APIRouter(prefix="/api/auth",
                   tags=["/api/auth"]
                   )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_token(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        token_data = decode_token(token)
        if token_data is None:
            raise CredentialsException()

    except InvalidTokenError:
        raise CredentialsException()

    return token_data


async def get_current_active_token(
        current_token: Annotated[TokenData, Depends(get_current_token)],
):
    if not await redis_dict.compare_version(current_token.participant_id, current_token.token_version):
        raise InactiveUserException()

    return current_token


async def get_token_from_websocket(websocket: WebSocket) -> str:
    """Получение токена из WebSocket соединения"""
    # Пробуем получить токен из query параметров
    token = websocket.query_params.get("token")

    # Если нет в query, пробуем из заголовков
    if not token:
        auth_header = websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")

    if not token:
        await websocket.close()
        raise CredentialsWSException()

    return token


async def get_current_token_ws(websocket: WebSocket):
    """Проверка токена для WebSocket"""
    try:
        token = await get_token_from_websocket(websocket)
        token_data = decode_token(token)  # ваша функция декодирования

        if token_data is None:
            await websocket.close()
            raise CredentialsWSException()

    except InvalidTokenError:
        await websocket.close()
        raise CredentialsWSException()

    return token_data


async def get_current_active_token_ws(
        websocket: WebSocket,
        current_token: Annotated[TokenData, Depends(get_current_token_ws)],
):
    """Проверка активного токена для WebSocket"""
    if not await redis_dict.compare_version(current_token.participant_id, current_token.token_version):
        await websocket.close()
        raise InactiveUserWSException()

    return current_token


@router.post("/login", response_model=Token)
async def login_for_access_token(
        response: Response,
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    user_data = await authenticate_user(form_data.username, form_data.password)

    if not user_data:
        raise IncorrectUserDataException()

    refresh_token_expires = get_datetime_expire(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    refresh_token_data = await create_refresh_token(user_data.id, refresh_token_expires)
    if refresh_token_data is None:
        raise IncorrectUserDataException()

    refresh_token_response = f"{refresh_token_data.token_id}.{refresh_token_data.token}"
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token_response,
        httponly=True,
        secure=True,
        samesite="strict",
        expires=refresh_token_expires,
    )

    token_version = await redis_dict.get_or_create(user_data.participant_id)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user_data.participant_id),
            "participant_id": str(user_data.participant_id),
            "organization_id": str(user_data.organization_id),
            "role": user_data.role.value,
            "token_id": str(refresh_token_data.token_id),
            "token_version": str(token_version)
        },
        expires_delta=access_token_expires,
    )

    return Token(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=Token)
async def refresh_token(request: Request):
    refresh_token_response = request.cookies.get(REFRESH_COOKIE_NAME)

    if not refresh_token_response:
        raise MissingRefreshTokenException()

    try:
        token_id, token = refresh_token_response.split(".")
        token_id = int(token_id)
    except Exception:
        raise InvalidRefreshTokenException()

    user_data = await check_refresh_token(RefreshTokenSchema(token_id=token_id, token=token))
    if user_data is None:
        raise InvalidRefreshTokenException()

    token_version = await redis_dict.get_or_create(participant_id=user_data.participant_id)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user_data.participant_id),
            "participant_id": str(user_data.participant_id),
            "organization_id": str(user_data.organization_id),
            "role": user_data.role.value,
            "token_id": str(token_id),
            "token_version": str(token_version)
        },
        expires_delta=access_token_expires,
    )

    return Token(access_token=access_token, token_type="bearer")


@router.get("/sessions")
async def get_sessions(
        current_token: Annotated[TokenData, Depends(get_current_active_token)]
):
    user_id = await Repository.get_user_id_by_participant_id(current_token.participant_id)
    result = await Repository.get_active_sessions(user_id=user_id)
    return result


@router.delete("/sessions/current")
async def revoke_current_session(
        response: Response,
        current_token: Annotated[TokenData, Depends(get_current_active_token)]
):
    user_id = await Repository.get_user_id_by_participant_id(current_token.participant_id)

    await Repository.revoke_session(
        token_id=current_token.token_id,
        user_id=user_id
    )

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="strict"
    )

    return


@router.delete("/sessions/{token_id}")
async def revoke_session(
        token_id: int,
        response: Response,
        current_token: Annotated[TokenData, Depends(get_current_active_token)]
):
    user_id = await Repository.get_user_id_by_participant_id(current_token.participant_id)

    success = await Repository.revoke_session(
        token_id=token_id,
        user_id=user_id
    )

    if current_token.token_id == token_id:
        response.delete_cookie(
            key=REFRESH_COOKIE_NAME,
            httponly=True,
            secure=True,
            samesite="strict"
        )

    return


@router.delete("/sessions")
async def revoke_all_sessions(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        response: Response
):
    user_id = await Repository.get_user_id_by_participant_id(current_token.participant_id)

    await Repository.revoke_all_sessions(user_id)

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="strict"
    )

    return


def generate_login() -> str:
    login = generate()
    return login.replace("-", "_")


def generate_password() -> str:
    words = generate().split("-")
    return words[0].capitalize() + words[1] + str(secrets.randbelow(900) + 100) + secrets.choice(
        "!@#$%") + secrets.choice(string.ascii_uppercase)


@router.post("/register")
async def register(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        email: str,
        role: AddOrganizationParticipantsEnum,
) -> NameInOrganization:
    email = await validate_receiver_email(email=email)
    if email is None:
        raise InvalidEmailException()

    if current_token.role == UserRoleEnum.leader:
        raise LeaderCannotAddNewUserException()

    user_add_data = await Repository.get_user_by_email(email=email)
    if user_add_data is None:
        password = generate_password()
        password_hash = get_password_hash(password)
        while True:
            login = generate_login()
            user_data = await Repository.create_organization_user(login=login, password_hash=password_hash, email=email)
            if user_data is not None:
                break

        data = await Repository.add_organization_participant(
            organization_id=current_token.organization_id,
            user_id=user_data.id,
            name=user_data.login,
            role=UserRoleEnum(role.value)
        )
    else:
        user_participant_add_data = await Repository.get_participant(user_id=user_add_data.id)
        if user_participant_add_data is not None:
            raise CannotAddUserAnotherOrganizationException()

        password = generate_password()
        password_hash = get_password_hash(password)
        user_data = await Repository.change_user_password(user_id=user_add_data.id, password_hash=password_hash)
        if user_data is None:
            raise InvalidEmailException()

        data = await Repository.add_organization_participant(
            organization_id=current_token.organization_id,
            user_id=user_data.id,
            name=user_data.login,
            role=UserRoleEnum(role.value)
        )
        login = user_add_data.login
    try:
        await send_email(
            receiver_email=email,
            subject="Welcome to Clik!",
            body=f"Your login: {login}, password: {password}"
        )
    except Exception as e:
        await Repository.delete_organization_participants(participant_id=data.id)
        raise EmailSendException()
    organization_data = await Repository_Organization.get_organization_info(
        organization_id=current_token.organization_id
    )
    return NameInOrganization(
        name=login,
        username=login,
        email=email,
        organization_name=organization_data.organization_name,
        role=UserRoleEnum(role.value)
    )


@router.post("/reset_password")
async def register(
        email: str,
) -> None:
    email = await validate_receiver_email(email=email)
    if email is None:
        return

    user_add_data = await Repository.get_user_by_email(email=email)
    if user_add_data is None:
        return

    user_participant_add_data = await Repository.get_participant(user_id=user_add_data.id)
    if user_participant_add_data is None:
        return

    password = generate_password()
    password_hash = get_password_hash(password)

    user_data = await Repository.change_user_password(user_id=user_add_data.id, password_hash=password_hash)
    if user_data is None:
        return

    try:
        await send_email(
            receiver_email=email,
            subject="Clik reset password!",
            body=f"Your login: {user_add_data.login}, password: {password}"
        )
    except Exception as e:
        raise EmailSendException()
    await redis_dict.increment(user_participant_add_data.participant_id)
    return

@router.get("/test/token_check/")
async def read_users_me(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
):
    return current_token


@router.get("/test/create_organization/")
async def read_users_me(
        email: str,
        login: str,
        password: str
):
    if len(email) < 8 or len(email) > 32:
        raise HTTPException(status_code=400, detail="8 < email < 32")
    if len(login) < 8 or len(login) > 32:
        raise HTTPException(status_code=400, detail="8 < login < 32")
    if len(password) < 8 or len(password) > 32:
        raise HTTPException(status_code=400, detail="8 < password < 32")

    password_hash = get_password_hash(password)

    user_data = await Repository.create_organization_user(login=login, password_hash=password_hash, email=email)
    if user_data is None:
        raise HTTPException(status_code=400, detail="invalid email or login")

    organization_data = await Repository.add_new_organization(organization_name=login, organization_description="")

    data_add = await Repository.add_organization_participant(
        organization_id=organization_data.id,
        user_id=user_data.id,
        name=login,
        role=UserRoleEnum.organizer
    )

    return {"organization_id": data_add.organization_id}


@router.get("/test/create_organization_participant/")
async def read_users_me(
        email: str,
        login: str,
        password: str,
        organization_id: int,
        role: UserRoleEnum = UserRoleEnum.organizer
):
    if len(email) < 8 or len(email) > 32:
        raise HTTPException(status_code=400, detail="8 < email < 32")
    if len(login) < 8 or len(login) > 32:
        raise HTTPException(status_code=400, detail="8 < login < 32")
    if len(password) < 8 or len(password) > 32:
        raise HTTPException(status_code=400, detail="8 < password < 32")

    password_hash = get_password_hash(password)

    user_data = await Repository.create_organization_user(login=login, password_hash=password_hash, email=email)
    if user_data is None:
        raise HTTPException(status_code=400, detail="invalid email or login")

    data_add = await Repository.add_organization_participant(
        organization_id=organization_id,
        user_id=user_data.id,
        name=login,
        role=role
    )

    return {"organization_id": data_add.organization_id}


@router.get("/test/token_version/")
async def get_token_version(
        participant_id: int
) -> int | None:
    return await redis_dict.get(participant_id=participant_id)