from fastapi import APIRouter, Depends
from typing import Annotated

from auth.redis_dict import redis_dict
from auth.router import get_current_active_token
from auth.schemas import TokenData
from exceptions import OrganizationNotFoundException, InactiveUserException, NameTooLongException, \
    OrganizationNameTooLongException, OrganizationDescriptionTooLongException, \
    OnlyOrganizerCanChangeDescriptionException, UserNotFoundInOrganizationException, \
    UsersInDifferentOrganizationException, CannotChangeOwnRoleException, \
    InsufficientRolePermissionsToChangeRoleException, AdminCanOnlyChangeLeaderException

from organizations.schemas import UserRole, NameInOrganization, OrganizationName, \
    FilterListOrganizationParticipantsEnum, ListOrganizationParticipants, ChangeRoleEnum, UserRoleEnum
from organizations.repository import Repository

router = APIRouter(
    prefix="/api/organization",
    tags=["/api/organization"]
)


@router.get("/me/role")
async def get_me_role(
        current_token: Annotated[TokenData, Depends(get_current_active_token)]
) -> UserRole:
    return UserRole(role=current_token.role)


@router.get("/me/name")
async def get_me_name(
        current_token: Annotated[TokenData, Depends(get_current_active_token)]
) -> NameInOrganization:
    data_organization = await Repository.get_organization_info(organization_id=current_token.organization_id)
    if data_organization is None:
        raise OrganizationNotFoundException()

    data_user = await Repository.get_name_and_login_by_participant_id(participant_id=current_token.participant_id)
    if data_user is None:
        raise InactiveUserException()

    return NameInOrganization(
        name=data_user.name,
        username=data_user.username,
        email=data_user.email,
        organization_name=data_organization.organization_name,
        role=current_token.role
    )


@router.patch("/me/name")
async def patch_me_name(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        name: str
) -> NameInOrganization:
    if len(name) < 3 or len(name) > 32:
        raise NameTooLongException()

    data_organization = await Repository.get_organization_info(organization_id=current_token.organization_id)
    if data_organization is None:
        raise OrganizationNotFoundException()

    data_user = await Repository.get_name_and_login_by_participant_id(participant_id=current_token.participant_id)
    if data_user is None:
        raise InactiveUserException()

    data_organization_participant = await Repository.change_name_on_organization(
        participant_id=current_token.participant_id,
        name=name
    )
    if data_organization_participant is None:
        raise InactiveUserException()

    return NameInOrganization(
        name=data_organization_participant.name,
        username=data_user.username,
        email=data_user.email,
        organization_name=data_organization.organization_name,
        role=current_token.role
    )


@router.get("/description")
async def get_organization_description(
        current_token: Annotated[TokenData, Depends(get_current_active_token)]
) -> OrganizationName:
    data_organization = await Repository.get_organization_info(organization_id=current_token.organization_id)
    if data_organization is None:
        raise OrganizationNotFoundException()

    return data_organization


@router.patch("/description")
async def patch_organization_description(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        organization_name: str,
        organization_description: str
) -> OrganizationName:
    if len(organization_name) < 3 or len(organization_name) > 32:
        raise OrganizationNameTooLongException()

    if len(organization_description) > 200:
        raise OrganizationDescriptionTooLongException()

    if current_token.role != UserRoleEnum.organizer:
        raise OnlyOrganizerCanChangeDescriptionException()

    data_organization = await Repository.change_organization_info(
        organization_id=current_token.organization_id,
        organization_name=organization_name,
        organization_description=organization_description
    )
    if data_organization is None:
        raise OrganizationNotFoundException()

    return data_organization


@router.get("/participants")
async def get_organization_participants(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        filter: FilterListOrganizationParticipantsEnum
) -> ListOrganizationParticipants:
    result = await Repository.get_organization_participants(
        participant_id=current_token.participant_id,
        organization_id=current_token.organization_id,
        filter=filter
    )
    return result


@router.patch("/participant_change_role")
async def change_role_organization_participant(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        participant_id: int,
        role: ChangeRoleEnum
) -> NameInOrganization:
    if current_token.role == UserRoleEnum.leader:
        raise InsufficientRolePermissionsToChangeRoleException()

    data_organization_participant_to = await Repository.get_name_role_organization_id_by_organization_participant_id(
        participant_id=participant_id
    )

    if data_organization_participant_to is None:
        raise UserNotFoundInOrganizationException()
    if current_token.organization_id != data_organization_participant_to.organization_id:
        raise UsersInDifferentOrganizationException()
    if current_token.participant_id == data_organization_participant_to.participant_id:
        raise CannotChangeOwnRoleException()

    data_user_to = await Repository.get_name_and_login_by_participant_id(
        participant_id=data_organization_participant_to.participant_id)
    if data_user_to is None:
        raise UserNotFoundInOrganizationException()

    data_organization = await Repository.get_organization_info(organization_id=current_token.organization_id)
    if data_organization is None:
        raise OrganizationNotFoundException()

    data_result = None

    if current_token.role == UserRoleEnum.admin:
        if data_organization_participant_to.role == UserRoleEnum.leader:
            data_result = await Repository.change_role_on_organization(participant_id=participant_id, role=role)
        else:
            raise AdminCanOnlyChangeLeaderException()
    if current_token.role == UserRoleEnum.organizer:
        data_result = await Repository.change_role_on_organization(participant_id=participant_id, role=role)

    if data_result is None:
        raise UserNotFoundInOrganizationException()

    await redis_dict.increment(participant_id)
    return NameInOrganization(
        name=data_result.name,
        username=data_user_to.username,
        email=data_user_to.email,
        organization_name=data_organization.organization_name,
        role=data_result.role
    )

# @router.post("/participants")
# async def add_organization_participants(
#         telegram_id: int,
#         participant_username: str,
#         role: AddOrganizationParticipantsEnum
# ) -> NameInOrganization:
#     user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
#     if user_id is None:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     data_organization_participant = await Repository.get_name_role_organization_id(user_id)
#     if data_organization_participant is None:
#         raise HTTPException(status_code=404, detail="User not found on organization")
#
#     if data_organization_participant.role == UserRoleEnum.leader:
#         raise HTTPException(status_code=404, detail="Only admin and organizer can add participants in organization")
#
#     data_organization = await Repository.get_organization_info(data_organization_participant.organization_id)
#     if data_organization is None:
#         raise HTTPException(status_code=404, detail="Organization not found")
#
#     participant_username = participant_username[1:] if participant_username.startswith('@') else participant_username
#     user_id_add = await Repository.get_user_id_by_username(participant_username)
#     if user_id_add is None:
#         raise HTTPException(status_code=409, detail="User to add not found")
#     name = user_id_add.username if len(user_id_add.username) != 0 else "Аноним"
#
#     data_organization_participant_add = await Repository.get_name_role_organization_id(user_id_add.user_id)
#     if data_organization_participant_add is not None:
#         raise HTTPException(status_code=404, detail="You cannot add a user who is a member of another organization.")
#
#     data_add = await Repository.add_organization_participant(
#         organization_id=data_organization_participant.organization_id, user_id=user_id_add.user_id, name=name,
#         role=UserRoleEnum(role.value))
#
#     return NameInOrganization(name=data_add.name, username=user_id_add.username,
#                               organization_name=data_organization.organization_name, role=data_add.role)
#
#
# @router.post("/participants2")
# async def add_organization_participants2(
#         telegram_id: int,
#         participant_telegram_id: int,
#         role: AddOrganizationParticipantsEnum
# ) -> NameInOrganization:
#     user_id = await Repository.get_user_id_by_telegram_id(telegram_id)
#     if user_id is None:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     data_organization_participant = await Repository.get_name_role_organization_id(user_id)
#     if data_organization_participant is None:
#         raise HTTPException(status_code=404, detail="User not found on organization")
#
#     if data_organization_participant.role == UserRoleEnum.leader:
#         raise HTTPException(status_code=404, detail="Only admin and organizer can add participants in organization")
#
#     data_organization = await Repository.get_organization_info(data_organization_participant.organization_id)
#     if data_organization is None:
#         raise HTTPException(status_code=404, detail="Organization not found")
#
#     user_id_add = await Repository.get_user_id_and_username_by_telegram_id(participant_telegram_id)
#     if user_id_add is None:
#         raise HTTPException(status_code=409, detail="User to add not found")
#     name = user_id_add.username if len(user_id_add.username) != 0 else "Аноним"
#
#     data_organization_participant_add = await Repository.get_name_role_organization_id(user_id_add.user_id)
#     if data_organization_participant_add is not None:
#         raise HTTPException(status_code=404, detail="You cannot add a user who is a member of another organization.")
#
#     data_add = await Repository.add_organization_participant(
#         organization_id=data_organization_participant.organization_id, user_id=user_id_add.user_id, name=name,
#         role=UserRoleEnum(role.value))
#
#     return NameInOrganization(name=data_add.name, username=user_id_add.username,
#                               organization_name=data_organization.organization_name, role=data_add.role)
#

# @router.post("/create")
# async def create_organization(
#         telegram_id: int
# ) -> OrganizationId:
#     user_data = await Repository.get_user_id_and_username_by_telegram_id(telegram_id)
#     if user_data is None:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     data_organization_participant_add = await Repository.get_name_role_organization_id(user_data.user_id)
#     if data_organization_participant_add is not None:
#         raise HTTPException(status_code=404, detail="You cannot add a user who is a member of another organization.")
#
#     name = user_data.username if len(user_data.username) != 0 else "Аноним"
#     organization_name = user_data.username if len(user_data.username) != 0 else "Без названия"
#
#     organization_data = await Repository.add_new_organization(organization_name=organization_name,
#                                                               organization_description="")
#
#     data_add = await Repository.add_organization_participant(
#         organization_id=organization_data.id, user_id=user_data.user_id, name=name,
#         role=UserRoleEnum.organizer)
#
#     return OrganizationId(organization_id=data_add.organization_id)
