import enum

from pydantic import BaseModel

from models import UserRoleEnum


class UserRole(BaseModel):
    role: UserRoleEnum


class NameInOrganization(BaseModel):
    name: str
    username: str
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


class OrganizationId(BaseModel):
    organization_id: int


class UserIdUsername(BaseModel):
    user_id: int
    username: str

class OrganizationParticipantIdOrganizationId(BaseModel):
    organization_participant_id: int
    organization_id: int

class OrganizationParticipantIdOrganizationIdRole(BaseModel):
    organization_participant_id: int
    organization_id: int
    role: UserRoleEnum

class NameRoleOrganizationId(BaseModel):
    name: str
    role: UserRoleEnum
    organization_id: int


class NameRoleOrganizationIdAndUserId(NameRoleOrganizationId):
    user_id: int


class FilterListOrganizationParticipantsEnum(str, enum.Enum):
    all = "all"
    leader = "leader"
    admin = "admin"
    organizer = "organizer"


class ChangeRoleEnum(str, enum.Enum):
    leader = "leader"
    admin = "admin"
    remote = "remote"


class AddOrganizationParticipantsEnum(str, enum.Enum):
    leader = "leader"
    admin = "admin"
