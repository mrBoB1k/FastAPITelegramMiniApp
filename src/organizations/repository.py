from sqlalchemy import select, delete
from database import new_session
from models import *

from organizations.schemas import UserRole, UserIdUsername, NameRoleOrganizationId, OrganizationName, \
    ListOrganizationParticipants, FilterListOrganizationParticipantsEnum, OrganizationParticipantData, \
    NameRoleOrganizationIdAndUserId, ChangeRoleEnum, OrganizationParticipantIdOrganizationId, \
    OrganizationParticipantIdOrganizationIdRole


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
    async def get_user_id_by_username(cls, username: str) -> UserIdUsername | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id, User.username).where(User.username == username)
            )
            rows = result.all()
            if len(rows) != 1:
                return None
            row = rows[0]
            user_id, username = row
            return UserIdUsername(user_id=user_id, username=username)

    @classmethod
    async def get_user_id_and_username_by_telegram_id(cls, telegram_id: int) -> UserIdUsername | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id, User.username).where(User.telegram_id == telegram_id)
            )
            row = result.one_or_none()
            if row is None:
                return None
            user_id, username = row
            return UserIdUsername(user_id=user_id, username=username)

    @classmethod
    async def get_user_id_and_username_by_participant_id(cls, participant_id: int) -> UserIdUsername | None:
        async with new_session() as session:
            result = await session.execute(
                select(User.id, User.username)
                .select_from(OrganizationParticipant)
                .join(User, OrganizationParticipant.user_id == User.id)
                .where(OrganizationParticipant.id == participant_id)
            )
            row = result.one_or_none()
            if row is None:
                return None
            user_id, username = row
            return UserIdUsername(user_id=user_id, username=username)

    @classmethod
    async def get_role_on_organizations_by_user_id(cls, user_id: int) -> UserRole:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant.role).where(OrganizationParticipant.user_id == user_id,
                                                           OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.scalar_one_or_none()
            if row is None:
                return UserRole(role=UserRoleEnum.participant)
            else:
                return UserRole(role=row)

    @classmethod
    async def get_organization_participant_id_by_user_id(cls, user_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant.id).where(OrganizationParticipant.user_id == user_id,
                                                         OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.scalar_one_or_none()
            return row

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
    async def get_organization_participant_id_and_organization_id_and_role_by_user_id(cls,
                                                                                      user_id: int) -> OrganizationParticipantIdOrganizationIdRole | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant.id, OrganizationParticipant.organization_id,
                       OrganizationParticipant.role)
                .where(OrganizationParticipant.user_id == user_id,
                       OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.one_or_none()
            if row is None:
                return None
            organization_participant_id, organization_id, role = row
            return OrganizationParticipantIdOrganizationIdRole(organization_participant_id=organization_participant_id,
                                                               organization_id=organization_id, role=role)

    @classmethod
    async def get_name_role_organization_id(cls, user_id: int) -> NameRoleOrganizationId | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant.name, OrganizationParticipant.role,
                       OrganizationParticipant.organization_id).where(OrganizationParticipant.user_id == user_id,
                                                                      OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.one_or_none()
            if row is None:
                return None
            name, role, organization_id = row
            return NameRoleOrganizationId(name=name, role=role, organization_id=organization_id)

    @classmethod
    async def get_name_role_organization_id_by_organization_participant_id(cls,
                                                                           participant_id: int) -> NameRoleOrganizationIdAndUserId | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant.name, OrganizationParticipant.role,
                       OrganizationParticipant.organization_id, OrganizationParticipant.user_id).where(
                    OrganizationParticipant.id == participant_id,
                    OrganizationParticipant.role != UserRoleEnum.remote)
            )

            row = result.one_or_none()
            if row is None:
                return None
            name, role, organization_id, user_id = row
            return NameRoleOrganizationIdAndUserId(name=name, role=role, organization_id=organization_id,
                                                   user_id=user_id)

    @classmethod
    async def get_organization_id_by_organization_participant_id(cls, participant_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant.organization_id)
                .where(OrganizationParticipant.id == participant_id)
            )

            organization_id = result.scalar_one_or_none()
            return organization_id

    @classmethod
    async def change_name_on_organization(cls, user_id: int, name: str) -> NameRoleOrganizationId | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant).where(OrganizationParticipant.user_id == user_id,
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

    @classmethod
    async def get_organization_info(cls, organization_id: int) -> OrganizationName | None:
        async with new_session() as session:
            result = await session.execute(
                select(Organization.name, Organization.description).where(Organization.id == organization_id)
            )

            row = result.one_or_none()
            if row is None:
                return None
            name, description = row
            return OrganizationName(organization_name=name, organization_description=description)

    @classmethod
    async def change_organization_info(cls, organization_id: int, organization_name: str,
                                       organization_description: str) -> OrganizationName | None:
        async with new_session() as session:
            result = await session.execute(
                select(Organization).where(Organization.id == organization_id)
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
            user_id: int,
            filter: FilterListOrganizationParticipantsEnum
    ) -> ListOrganizationParticipants | None:
        async with new_session() as session:
            # Сначала находим organization_id, где пользователь состоит
            # и его роль не remote
            user_org_subquery = (
                select(OrganizationParticipant.organization_id)
                .join(User, OrganizationParticipant.user_id == User.id)
                .where(
                    OrganizationParticipant.user_id == user_id,
                    OrganizationParticipant.role != UserRoleEnum.remote
                )
            )

            # Проверяем, есть ли у пользователя организации с подходящей ролью
            org_check = await session.execute(
                select(func.count()).select_from(user_org_subquery.subquery())
            )
            org_count = org_check.scalar()

            # Если пользователь не состоит в организациях с ролью не remote, возвращаем None
            if org_count == 0:
                return None

            # Основной запрос для получения участников организаций пользователя
            query = (
                select(
                    OrganizationParticipant.id,
                    OrganizationParticipant.name,
                    User.username,
                    OrganizationParticipant.role,
                    OrganizationParticipant.user_id
                )
                .join(User, OrganizationParticipant.user_id == User.id)
                .where(
                    OrganizationParticipant.organization_id.in_(user_org_subquery),
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
                    is_you=(participant.user_id == user_id)
                ))

            return ListOrganizationParticipants(participants=participants_list)

    @classmethod
    async def add_organization_participant(
            cls,
            organization_id: int,
            user_id: int,
            name: str,
            role: UserRoleEnum
    ) -> OrganizationParticipant:
        async with new_session() as session:
            async with session.begin():
                # Создаем новую запись участника организации
                new_participant = OrganizationParticipant(
                    organization_id=organization_id,
                    user_id=user_id,
                    name=name,
                    role=role
                )

                # Добавляем в сессию
                session.add(new_participant)
                await session.flush()  # Получаем ID созданной записи
                await session.refresh(new_participant)  # Обновляем объект из БД

                return new_participant

    @classmethod
    async def add_new_organization(
            cls,
            organization_name: str,
            organization_description: str,
    ) -> Organization:
        async with new_session() as session:
            async with session.begin():
                # Создаем новую запись участника организации
                new_organization = Organization(
                    name=organization_name,
                    description=organization_description
                )

                # Добавляем в сессию
                session.add(new_organization)
                await session.flush()  # Получаем ID созданной записи
                await session.refresh(new_organization)  # Обновляем объект из БД

                return new_organization
