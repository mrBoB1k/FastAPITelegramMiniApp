from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response, Request, WebSocket, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from namer import generate
import string
import secrets

from models import UserRoleEnum
from exceptions import CredentialsException, InactiveUserException, IncorrectUserDataException, \
    InvalidRefreshTokenException, MissingRefreshTokenException, CredentialsWSException, InactiveUserWSException, \
    LeaderCannotAddNewUserException, CannotAddUserAnotherOrganizationException, InvalidEmailException, \
    EmailSendException, InvalidLoginException, InvalidPasswordException
from organizations.schemas import NameInOrganization
from send_email import send_email, validate_receiver_email
from organizations.repository import Repository as Repository_Organization
from config import URL_FRONT

from auth.repository import Repository
from auth.schemas import Token, RefreshTokenSchema, TokenData, AddOrganizationParticipantsEnum, VkTokenData, \
    VkDataSchema, VkTokenSchema, ParticipantTokenData
from auth.untils import authenticate_user, create_access_token, create_refresh_token, decode_token, get_datetime_expire, \
    check_refresh_token, get_password_hash, decode_base64, is_valid_vk_token, is_valid_vk_ts, generate_vk_sign, \
    decode_token_for_participant, decode_token_for_register, decode_token_for_reset
from auth.auth_config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_COOKIE_NAME, REFRESH_TOKEN_EXPIRE_DAYS, VK_APP_ID, \
    VK_CLIENT_SECRET
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
        token_data = decode_token(token)

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


async def get_current_vk_token_for_participant_ws(websocket: WebSocket, vk_data: VkDataSchema):
    """Проверка токена для WebSocket"""
    try:
        vk_token = decode_base64(vk_data.vk_token)
        if not is_valid_vk_token(query=vk_token, secret=VK_CLIENT_SECRET):
            await websocket.close()
            raise CredentialsWSException()

        if not is_valid_vk_ts(vk_ts=vk_token["vk_ts"]):
            await websocket.close()
            raise CredentialsWSException()

        if int(vk_token["vk_app_id"]) != VK_APP_ID:
            await websocket.close()
            raise CredentialsWSException()

        vk_info = decode_base64(vk_data.vk_info)

        email = None
        if vk_data.vk_email is not None:
            vk_email = decode_base64(vk_data.vk_email)
            email_sign = generate_vk_sign(app_id=VK_APP_ID,
                                          api_secret=VK_CLIENT_SECRET,
                                          vk_user_id=vk_token["vk_user_id"],
                                          field_name="email",
                                          field_value=vk_email["email"]
                                          )
            if email_sign != vk_email["sign"]:
                await websocket.close()
                raise CredentialsWSException()
            email = vk_email["email"]

        phone = None
        if vk_data.vk_phone is not None:
            vk_phone = decode_base64(vk_data.vk_phone)
            phone_sign = generate_vk_sign(app_id=VK_APP_ID,
                                          api_secret=VK_CLIENT_SECRET,
                                          vk_user_id=vk_token["vk_user_id"],
                                          field_name="phone_number",
                                          field_value=vk_phone["phone_number"]
                                          )
            if phone_sign != vk_phone["sign"]:
                await websocket.close()
                raise CredentialsWSException()
            phone = vk_phone["phone_number"]

    except InvalidTokenError:
        await websocket.close()
        raise CredentialsWSException()

    return VkTokenSchema(
        vk_user_id=vk_token["vk_user_id"],
        first_name=vk_info["first_name"],
        last_name=vk_info["last_name"],
        email=email,
        phone_number=phone
    )


async def get_decoded_token(token: str, websocket: WebSocket):
    try:
        token_data = decode_token_for_participant(token)

        if token_data is None:
            await websocket.close()
            raise CredentialsWSException()

    except InvalidTokenError:
        await websocket.close()
        raise CredentialsWSException()

    return token_data

async def get_current_active_token_for_participant_ws(
        websocket: WebSocket,
) -> ParticipantTokenData:
    vk_token = websocket.query_params.get("vkToken")
    vk_info = websocket.query_params.get("vkInfo")
    vk_email = websocket.query_params.get("vkEmail")
    vk_phone = websocket.query_params.get("vkPhone")
    anonym_token = websocket.query_params.get("anonymToken")
    email_token = websocket.query_params.get("emailToken")

    if vk_token and vk_info:
        current_token = await get_current_vk_token_for_participant_ws(
            websocket,
            VkDataSchema(vk_token=vk_token, vk_info=vk_info,vk_email=vk_email,vk_phone=vk_phone)
        )
        user_info = await Repository.upsert_vk_user(
            vk_user_id=current_token.vk_user_id,
            first_name=current_token.first_name,
            last_name=current_token.last_name,
            email=current_token.email,
            phone_number=current_token.phone_number
        )
        user_id = user_info.user_id
    elif anonym_token:
        user_id =  await get_decoded_token(anonym_token, websocket)
    elif email_token:
        user_id = await get_decoded_token(email_token, websocket)
    else:
        await websocket.close()
        raise CredentialsWSException()

    return ParticipantTokenData(user_id=user_id)


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

@router.post("/email_login", response_model=Token)
async def login_for_email(email: str):
    email_user = await Repository.upsert_email_user(email=email)

    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={
            "sub": str(email_user.user_id),
            "user_id": str(email_user.user_id),
        },
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")

@router.post("/anonym_login", response_model=Token)
async def login_for_anonym():
    anonym_user = await Repository.create_anonym_user()

    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={
            "sub": str(anonym_user.id),
            "user_id": str(anonym_user.id),
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
        background_tasks: BackgroundTasks,
):
    email = await validate_receiver_email(email=email)
    if email is None:
        raise InvalidEmailException()

    if current_token.role == UserRoleEnum.leader:
        raise LeaderCannotAddNewUserException()

    user_add_data = await Repository.get_user_by_email(email=email)
    if user_add_data is None:
        token_expires = timedelta(minutes=60)
        token = create_access_token(
            data={
                "sub": str(email),
                "email": str(email),
                "organization_id": str(current_token.organization_id),
                "role": str(role.value),
            },
            expires_delta=token_expires,
        )
    else:
        user_participant_add_data = await Repository.get_participant(user_id=user_add_data.id)
        if user_participant_add_data is not None:
            raise CannotAddUserAnotherOrganizationException()
        token_expires = timedelta(minutes=60)
        token = create_access_token(
            data={
                "sub": str(email),
                "email": str(email),
                "organization_id": str(current_token.organization_id),
                "role": str(role.value),
            },
            expires_delta=token_expires,
        )

    background_tasks.add_task(
        send_email,
        receiver_email=email,
        subject="Добро пожаловать в Clik!",
        body=f'Нажмите на эту ссылку, чтобы завершить регистрацию: {URL_FRONT}/first_reg?jwt={token}'
    )
    return

@router.post("/register/confirm")
async def register(
        token: str,
        login: str,
        password: str,
):
    token_data = decode_token_for_register(token)
    if token_data is None:
        raise CredentialsException()

    check_login = await Repository.check_login_exist(login=login)
    if check_login:
        raise InvalidLoginException()

    len_login = len(login)
    len_password = len(password)

    if len_login < 3 or len_password > 30:
        raise InvalidLoginException()

    if len_password < 8 or len_password > 15:
        raise InvalidPasswordException()

    user_add_data = await Repository.get_user_by_email(email=token_data.email)
    if user_add_data is None:
        password_hash = get_password_hash(password)
        user_data = await Repository.create_organization_user(login=login, password_hash=password_hash, email=token_data.email)
        if user_data is None:
            raise InvalidEmailException()

        data = await Repository.add_organization_participant(
            organization_id=token_data.organization_id,
            user_id=user_data.id,
            name=user_data.login,
            role=UserRoleEnum(token_data.role)
        )

    else:
        user_participant_add_data = await Repository.get_participant(user_id=user_add_data.id)
        if user_participant_add_data is not None:
            raise CannotAddUserAnotherOrganizationException()

        password_hash = get_password_hash(password)
        user_data = await Repository.change_user_password_and_login(user_id=user_add_data.id, password_hash=password_hash, login=login)
        if user_data is None:
            raise InvalidEmailException()

        data = await Repository.add_organization_participant(
            organization_id=token_data.organization_id,
            user_id=user_data.id,
            name=user_data.login,
            role=UserRoleEnum(token_data.role)
        )

    return

@router.post("/reset_password")
async def reset_password(
        email: str,
        background_tasks: BackgroundTasks,
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

    token_expires = timedelta(minutes=60)
    token = create_access_token(
        data={
            "sub": str(email),
            "user_id": str(user_add_data.id),
            "login": str(user_add_data.login),
            "email": str(email),
        },
        expires_delta=token_expires,
    )

    background_tasks.add_task(
        send_email,
        receiver_email=email,
        subject="Clik сбросить пароль.",
        body=f"Нажмите на эту ссылку, чтобы восстановить пароль: {URL_FRONT}/reset?jwt={token}"
    )
    return

@router.post("/reset_password/confirm")
async def register(
        token: str,
        password: str,
):
    user_id = decode_token_for_reset(token)
    if user_id is None:
        raise CredentialsException()

    len_password = len(password)
    if len_password < 8 or len_password > 15:
        raise InvalidPasswordException()

    password_hash = get_password_hash(password)
    user_data = await Repository.change_user_password(user_id=user_id, password_hash=password_hash)
    if user_data is None:
        raise InvalidEmailException()


    user_participant_add_data = await Repository.get_participant(user_id=user_id)
    if user_participant_add_data is None:
        return
    await redis_dict.increment(user_participant_add_data.participant_id)
    await Repository.revoke_all_sessions(user_id)

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
