from datetime import datetime
from pydantic import BaseModel
import enum

from models import UserRoleEnum


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenSchema(BaseModel):
    participant_id: int
    organization_id: int
    role: UserRoleEnum


class TokenData(TokenSchema):
    token_id: int
    token_version: int

class TokenRegisterData(BaseModel):
    email: str
    organization_id: int
    role: str

class VkDataSchema(BaseModel):
    vk_token: str
    vk_info: str
    vk_email: str | None = None
    vk_phone: str | None = None

class VkTokenSchema(BaseModel):
    vk_user_id: int
    first_name: str
    last_name: str
    email: str | None = None
    phone_number: str | None = None

class VkTokenData(VkTokenSchema):
    user_id: int

class ParticipantTokenData(BaseModel):
    user_id: int

class VkUserInfo(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    email: str | None = None
    phone_number: str | None = None

class RefreshTokenSchema(BaseModel):
    token_id: int
    token: str


class UserSchema(BaseModel):
    id: int
    login: str
    email: str


class UserInDB(UserSchema):
    password_hash: str


class AuthenticateUserSchema(UserSchema):
    participant_id: int
    organization_id: int
    role: UserRoleEnum


class ActiveSessionInfo(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime


class AddOrganizationParticipantsEnum(str, enum.Enum):
    leader = "leader"
    admin = "admin"
