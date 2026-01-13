from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from organizations.schemas import UserRole, NameInOrganization, OrganizationName, \
    FilterListOrganizationParticipantsEnum, ListOrganizationParticipants, ChangeRoleEnum, \
    AddOrganizationParticipantsEnum, OrganizationId, UserRoleEnum
from organizations.repository import Repository

router = APIRouter(
    prefix="/api/organization",
    tags=["/api/organization"]
)


@router.get("/me/role")
async def get_me_role(
        telegram_id: int
) -> UserRole:
    user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    role = await Repository.get_role_on_organizations_by_user_id(user_id)
    return role


@router.get("/me/name")
async def get_me_name(
        telegram_id: int
) -> NameInOrganization:
    data_user = await Repository.get_user_id_and_username_by_telegram_id(telegram_id)
    if data_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant = await Repository.get_name_role_organization_id(data_user.user_id)
    if data_organization_participant is None:
        raise HTTPException(status_code=404, detail="User not found on organization")

    data_organization = await Repository.get_organization_info(data_organization_participant.organization_id)
    if data_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    return NameInOrganization(name=data_organization_participant.name, username=data_user.username,
                              organization_name=data_organization.organization_name,
                              role=data_organization_participant.role)


@router.patch("/me/name")
async def patch_me_name(
        telegram_id: int,
        name: str
) -> NameInOrganization:
    if len(name) < 3 or len(name) > 32:
        raise HTTPException(status_code=400, detail="Name too long (name must be between 3 and 32 characters)")

    data_user = await Repository.get_user_id_and_username_by_telegram_id(telegram_id)
    if data_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant = await Repository.change_name_on_organization(data_user.user_id, name)
    if data_organization_participant is None:
        raise HTTPException(status_code=404, detail="User not found on organization")

    data_organization = await Repository.get_organization_info(data_organization_participant.organization_id)
    if data_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    return NameInOrganization(name=data_organization_participant.name, username=data_user.username,
                              organization_name=data_organization.organization_name,
                              role=data_organization_participant.role)


@router.get("/description")
async def get_organization_description(
        telegram_id: int
) -> OrganizationName:
    user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant = await Repository.get_name_role_organization_id(user_id)
    if data_organization_participant is None:
        raise HTTPException(status_code=404, detail="User not found on organization")

    data_organization = await Repository.get_organization_info(data_organization_participant.organization_id)
    if data_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    return data_organization


@router.patch("/description")
async def patch_organization_description(
        telegram_id: int,
        organization_name: str,
        organization_description: str
) -> OrganizationName:
    if len(organization_name) < 3 or len(organization_name) > 32:
        raise HTTPException(status_code=400,
                            detail="Organization name too long (Organization_name must be between 3 and 32 characters)")

    if len(organization_description) > 200:
        raise HTTPException(status_code=400,
                            detail="Organization description too long (organization_description must be between 0 and 200 characters)")

    user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant = await Repository.get_name_role_organization_id(user_id)
    if data_organization_participant is None:
        raise HTTPException(status_code=404, detail="User not found on organization")

    if data_organization_participant.role != UserRoleEnum.organizer:
        raise HTTPException(status_code=404, detail="Only organizer can change description")

    data_organization = await Repository.change_organization_info(data_organization_participant.organization_id,
                                                                  organization_name, organization_description)

    if data_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    return data_organization


@router.get("/participants")
async def get_organization_participants(
        telegram_id: int,
        filter: FilterListOrganizationParticipantsEnum
) -> ListOrganizationParticipants:
    user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await Repository.get_organization_participants(user_id, filter)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found on organization")

    return result


@router.patch("/participant_change_role")
async def change_role_organization_participant(
        telegram_id: int,
        participant_id: int,
        role: ChangeRoleEnum
) -> NameInOrganization:
    user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant_from = await Repository.get_name_role_organization_id(user_id)
    if data_organization_participant_from is None:
        raise HTTPException(status_code=404, detail="User_from not found on organization")

    data_organization_participant_to = await Repository.get_name_role_organization_id_by_organization_participant_id(
        participant_id)
    if data_organization_participant_to is None:
        raise HTTPException(status_code=404, detail="User_to not found on organization")

    if data_organization_participant_from.organization_id != data_organization_participant_to.organization_id:
        raise HTTPException(status_code=404, detail="User_from and User_to are in different organizations")

    if user_id == data_organization_participant_to.user_id:
        raise HTTPException(status_code=404, detail="You cannot change your own role")

    if data_organization_participant_from.role == UserRoleEnum.leader:
        raise HTTPException(status_code=404, detail="Only admin and organizer can change role")

    username_participant_to = await Repository.get_user_id_and_username_by_participant_id(participant_id)
    if username_participant_to is None:
        raise HTTPException(status_code=404, detail="User_to not found")

    data_organization = await Repository.get_organization_info(data_organization_participant_to.organization_id)
    if data_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    data_result = None

    if data_organization_participant_from.role == UserRoleEnum.admin:
        if data_organization_participant_to.role == UserRoleEnum.leader:
            data_result = await Repository.change_role_on_organization(participant_id, role)
        else:
            raise HTTPException(status_code=404, detail="Admin can only change the leader role")

    if data_organization_participant_from.role == UserRoleEnum.organizer:
        data_result = await Repository.change_role_on_organization(participant_id, role)

    if data_result is None:
        raise HTTPException(status_code=404, detail="Can problem to change role")

    result = NameInOrganization(name=data_result.name, username=username_participant_to.username,
                                organization_name=data_organization.organization_name, role=data_result.role)
    return result


@router.post("/participants")
async def add_organization_participants(
        telegram_id: int,
        participant_username: str,
        role: AddOrganizationParticipantsEnum
) -> NameInOrganization:
    user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant = await Repository.get_name_role_organization_id(user_id)
    if data_organization_participant is None:
        raise HTTPException(status_code=404, detail="User not found on organization")

    if data_organization_participant.role == UserRoleEnum.leader:
        raise HTTPException(status_code=404, detail="Only admin and organizer can add participants in organization")

    data_organization = await Repository.get_organization_info(data_organization_participant.organization_id)
    if data_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    participant_username = participant_username[1:] if participant_username.startswith('@') else participant_username
    user_id_add = await Repository.get_user_id_by_username(participant_username)
    if user_id_add is None:
        raise HTTPException(status_code=409, detail="User to add not found")
    name = user_id_add.username if len(user_id_add.username) != 0 else "Аноним"

    data_organization_participant_add = await Repository.get_name_role_organization_id(user_id_add.user_id)
    if data_organization_participant_add is not None:
        raise HTTPException(status_code=404, detail="You cannot add a user who is a member of another organization.")

    data_add = await Repository.add_organization_participant(
        organization_id=data_organization_participant.organization_id, user_id=user_id_add.user_id, name=name,
        role=UserRoleEnum(role.value))

    return NameInOrganization(name=data_add.name, username=user_id_add.username,
                              organization_name=data_organization.organization_name, role=data_add.role)

@router.post("/participants2")
async def add_organization_participants2(
        telegram_id: int,
        participant_telegram_id: int,
        role: AddOrganizationParticipantsEnum
) -> NameInOrganization:
    user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant = await Repository.get_name_role_organization_id(user_id)
    if data_organization_participant is None:
        raise HTTPException(status_code=404, detail="User not found on organization")

    if data_organization_participant.role == UserRoleEnum.leader:
        raise HTTPException(status_code=404, detail="Only admin and organizer can add participants in organization")

    data_organization = await Repository.get_organization_info(data_organization_participant.organization_id)
    if data_organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    user_id_add = await Repository.get_user_id_and_username_by_telegram_id(participant_telegram_id)
    if user_id_add is None:
        raise HTTPException(status_code=409, detail="User to add not found")
    name = user_id_add.username if len(user_id_add.username) != 0 else "Аноним"

    data_organization_participant_add = await Repository.get_name_role_organization_id(user_id_add.user_id)
    if data_organization_participant_add is not None:
        raise HTTPException(status_code=404, detail="You cannot add a user who is a member of another organization.")

    data_add = await Repository.add_organization_participant(
        organization_id=data_organization_participant.organization_id, user_id=user_id_add.user_id, name=name,
        role=UserRoleEnum(role.value))

    return NameInOrganization(name=data_add.name, username=user_id_add.username,
                              organization_name=data_organization.organization_name, role=data_add.role)

@router.post("/create")
async def create_organization(
        telegram_id: int
) -> OrganizationId:
    user_data = await Repository.get_user_id_and_username_by_telegram_id(telegram_id)
    if user_data is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_organization_participant_add = await Repository.get_name_role_organization_id(user_data.user_id)
    if data_organization_participant_add is not None:
        raise HTTPException(status_code=404, detail="You cannot add a user who is a member of another organization.")

    name = user_data.username if len(user_data.username) != 0 else "Аноним"
    organization_name = user_data.username if len(user_data.username) != 0 else "Без названия"

    organization_data = await Repository.add_new_organization(organization_name=organization_name,
                                                              organization_description="")

    data_add = await Repository.add_organization_participant(
        organization_id=organization_data.id, user_id=user_data.user_id, name=name,
        role=UserRoleEnum.organizer)

    return OrganizationId(organization_id=data_add.organization_id)
