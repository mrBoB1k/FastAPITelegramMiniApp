import enum
from pydantic import BaseModel

from models import UserRoleEnum


class UserRole(BaseModel):
    role: UserRoleEnum


class NameInOrganization(BaseModel):
    name: str
    username: str
    email: str
    organization_name: str
    role: UserRoleEnum


class OrganizationName(BaseModel):
    organization_name: str
    organization_description: str


class OrganizationParticipantData(BaseModel):
    name: str
    username: str
    role: UserRoleEnum
    id: int
    is_you: bool


class ListOrganizationParticipants(BaseModel):
    participants: list[OrganizationParticipantData]


class OrganizationParticipantIdOrganizationId(BaseModel):
    organization_participant_id: int
    organization_id: int


class NameRoleOrganizationId(BaseModel):
    name: str
    role: UserRoleEnum
    organization_id: int


class NameRoleOrganizationIdUserIdParticipantId(NameRoleOrganizationId):
    participant_id: int
    user_id: int

class NameUsername(BaseModel):
    name: str
    username: str #login in db
    email: str


class FilterListOrganizationParticipantsEnum(str, enum.Enum):
    all = "all"
    leader = "leader"
    admin = "admin"
    organizer = "organizer"


class ChangeRoleEnum(str, enum.Enum):
    leader = "leader"
    admin = "admin"
    remote = "remote"

