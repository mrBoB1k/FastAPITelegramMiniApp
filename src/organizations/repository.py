from sqlalchemy import select
from database import new_session
from models import *

from organizations.schemas import NameRoleOrganizationId, OrganizationName, ListOrganizationParticipants, \
    FilterListOrganizationParticipantsEnum, OrganizationParticipantData, ChangeRoleEnum, \
    OrganizationParticipantIdOrganizationId, NameUsername, NameRoleOrganizationIdUserIdParticipantId


class Repository:
    @classmethod
    async def get_user_id_by_telegram_id(cls, telegram_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id).where(User.telegram_id == telegram_id)
            )
            row = result.one_or_none()
            if row is None:
                return None
            return row[0]

    @classmethod
    async def get_organization_participant_id_and_organization_id_by_user_id(cls,
                                                                             user_id: int) -> OrganizationParticipantIdOrganizationId | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant.id, OrganizationParticipant.organization_id)
                .where(OrganizationParticipant.user_id == user_id,
                       OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.one_or_none()
            if row is None:
                return None
            organization_participant_id, organization_id = row
            return OrganizationParticipantIdOrganizationId(organization_participant_id=organization_participant_id,
                                                           organization_id=organization_id)

    @classmethod
    async def get_organization_info(cls, organization_id: int) -> OrganizationName | None:
        async with new_session() as session:
            result = await session.execute(
                select(Organization.name, Organization.description)
                .where(Organization.id == organization_id)
            )

            row = result.one_or_none()
            if row is None:
                return None
            name, description = row
            return OrganizationName(organization_name=name, organization_description=description)

    @classmethod
    async def get_name_and_login_by_participant_id(cls, participant_id: int) -> NameUsername | None:
        async with new_session() as session:
            result = await session.execute(
                select(
                    OrganizationParticipant.name,
                    OrganizationUser.login.label('username'),  # переименовываем для ясности
                    OrganizationUser.email
                )
                .join(
                    OrganizationUser,
                    OrganizationParticipant.user_id == OrganizationUser.id
                )
                .where(
                    OrganizationParticipant.id == participant_id,
                    OrganizationParticipant.role != UserRoleEnum.remote
                )
            )

            row = result.one_or_none()
            if row is None:
                return None

            # row - это кортеж (name, username)
            return NameUsername(name=row.name, username=row.username, email=row.email)

    @classmethod
    async def change_name_on_organization(cls, participant_id: int, name: str) -> NameRoleOrganizationId | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant)
                .where(
                    OrganizationParticipant.id == participant_id,
                    OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.scalar_one_or_none()
            if row is None:
                return None

            row.name = name
            await session.commit()
            await session.refresh(row)

            return NameRoleOrganizationId(name=row.name, role=row.role, organization_id=row.organization_id)

    @classmethod
    async def change_organization_info(cls, organization_id: int, organization_name: str,
                                       organization_description: str) -> OrganizationName | None:
        async with new_session() as session:
            result = await session.execute(
                select(Organization)
                .where(Organization.id == organization_id)
            )

            row = result.scalar_one_or_none()
            if row is None:
                return None

            row.name = organization_name
            row.description = organization_description
            await session.commit()
            await session.refresh(row)

            return OrganizationName(organization_name=row.name, organization_description=row.description)

    @classmethod
    async def get_organization_participants(
            cls,
            participant_id: int,
            organization_id: int,
            filter: FilterListOrganizationParticipantsEnum
    ) -> ListOrganizationParticipants | None:
        async with new_session() as session:
            # Основной запрос для получения участников организаций пользователя
            query = (
                select(
                    OrganizationParticipant.id,
                    OrganizationParticipant.name,
                    OrganizationUser.login.label('username'),
                    OrganizationParticipant.role,
                    OrganizationParticipant.user_id
                )
                .join(
                    OrganizationUser,
                    OrganizationParticipant.user_id == OrganizationUser.id)
                .where(
                    OrganizationParticipant.organization_id == organization_id,
                    OrganizationParticipant.role != UserRoleEnum.remote
                )
            )

            # Применяем фильтр по роли
            if filter != FilterListOrganizationParticipantsEnum.all:
                query = query.where(OrganizationParticipant.role == filter)

            # query = query.order_by(OrganizationParticipant.name)

            # Выполняем запрос
            result = await session.execute(query)
            participants_data = result.all()

            # Преобразуем в список участников
            participants_list = []
            for participant in participants_data:
                participants_list.append(OrganizationParticipantData(
                    name=participant.name,
                    username=participant.username,
                    role=participant.role,
                    id=participant.id,
                    is_you=(participant.id == participant_id)
                ))

            return ListOrganizationParticipants(participants=participants_list)

    @classmethod
    async def get_name_role_organization_id_by_organization_participant_id(
            cls,
            participant_id: int
    ) -> NameRoleOrganizationIdUserIdParticipantId | None:
        async with new_session() as session:
            result = await session.execute(
                select(
                    OrganizationParticipant.name,
                    OrganizationParticipant.role,
                    OrganizationParticipant.organization_id,
                    OrganizationParticipant.user_id)
                .where(
                    OrganizationParticipant.id == participant_id,
                    OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.one_or_none()
            if row is None:
                return None
            name, role, organization_id, user_id = row
            return NameRoleOrganizationIdUserIdParticipantId(
                participant_id=participant_id,
                name=name,
                role=role,
                organization_id=organization_id,
                user_id=user_id
            )

    @classmethod
    async def change_role_on_organization(cls, participant_id: int,
                                          role: ChangeRoleEnum) -> NameRoleOrganizationId | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant).where(OrganizationParticipant.id == participant_id,
                                                      OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.scalar_one_or_none()
            if row is None:
                return None

            row.role = UserRoleEnum(role.value)
            await session.commit()
            await session.refresh(row)

            return NameRoleOrganizationId(name=row.name, role=row.role, organization_id=row.organization_id)
