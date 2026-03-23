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
