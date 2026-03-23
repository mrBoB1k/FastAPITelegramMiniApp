from datetime import datetime, timezone

from sqlalchemy import select, update, func
from database import new_session
from auth.schemas import UserInDB, TokenSchema, UserSchema, ActiveSessionInfo
from models import *


class Repository:
    @classmethod
    async def get_user(cls, login: str) -> UserInDB | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationUser).where(OrganizationUser.login == login)
            )
            user = result.scalar_one_or_none()
            if user is None:
                return None

            return UserInDB(
                id=user.id,
                login=user.login,
                email=user.email,
                password_hash=user.password_hash
            )

    @classmethod
    async def get_user_by_id(cls, user_id: int) -> UserSchema | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationUser).where(OrganizationUser.id == user_id)
            )
            user = result.scalar_one_or_none()
            if user is None:
                return None

            return UserSchema(
                id=user.id,
                login=user.login,
                email=user.email,
            )

    @classmethod
    async def get_user_by_email(cls, email: str) -> UserSchema | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationUser).where(OrganizationUser.email == email)
            )
            user = result.scalar_one_or_none()
            if user is None:
                return None

            return UserSchema(
                id=user.id,
                login=user.login,
                email=user.email,
            )

    @classmethod
    async def get_participant(cls, user_id: int) -> TokenSchema | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant).where(OrganizationParticipant.user_id == user_id,
                                                      OrganizationParticipant.role != UserRoleEnum.remote)
            )
            participant = result.scalar_one_or_none()
            if participant is None:
                return None

            return TokenSchema(
                participant_id=participant.id,
                organization_id=participant.organization_id,
                role=participant.role
            )

    @classmethod
    async def get_user_id_by_participant_id(cls, participant_id: int) -> int | None:
        async with new_session() as session:
            result = await session.execute(
                select(OrganizationParticipant).where(OrganizationParticipant.id == participant_id,
                                                      OrganizationParticipant.role != UserRoleEnum.remote)
            )
            participant = result.scalar_one_or_none()
            if participant is None:
                return None

            return participant.user_id

    @classmethod
    async def create_session(cls, user_id: int, token_hash: str, expires_at: datetime) -> Session | None:
        async with new_session() as session:
            async with session.begin():
                # Преобразуем aware datetime в naive (UTC), убираем tzinfo
                if expires_at.tzinfo is not None:
                    # Конвертируем в UTC и делаем naive
                    expires_at_naive = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                    expires_at_naive = expires_at  # уже naive

                # Создаем новую сессию
                new_session_record = Session(
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at_naive
                    # created_at заполнится автоматически из server_default
                    # revoked_at по умолчанию None
                )

                session.add(new_session_record)
                await session.flush()
                await session.refresh(new_session_record)

                return new_session_record

    @classmethod
    async def get_valid_session(cls, token_id: int) -> Session | None:
        async with new_session() as db_session:
            query = (
                select(Session)
                .where(
                    Session.id == token_id,
                    Session.revoked_at.is_(None),
                    Session.expires_at > func.now()  # Не истекла
                )
            )
            return await db_session.scalar(query)

    @classmethod
    async def revoke_session(cls, token_id: int, user_id: int) -> bool:
        async with new_session() as session:
            async with session.begin():
                query = (
                    update(Session)
                    .where(
                        Session.id == token_id,
                        Session.user_id == user_id,
                        Session.revoked_at.is_(None)
                    )
                    .values(revoked_at=func.now())
                )

                result = await session.execute(query)

                return result.rowcount > 0

    @classmethod
    async def revoke_all_sessions(cls, user_id: int) -> bool:
        async with new_session() as session:
            async with session.begin():
                query = (
                    update(Session)
                    .where(
                        Session.user_id == user_id,
                        Session.revoked_at.is_(None)
                    )
                    .values(revoked_at=func.now())
                )

                result = await session.execute(query)

                return result.rowcount > 0

    @classmethod
    async def get_active_sessions(
            cls,
            user_id: int,
            include_expired: bool = False
    ) -> list[ActiveSessionInfo]:
        async with new_session() as session:
            query = (
                select(
                    Session.id,
                    Session.created_at,
                    Session.expires_at
                )
                .where(
                    Session.user_id == user_id,
                    Session.revoked_at.is_(None)
                )
            )

            # По умолчанию исключаем истекшие сессии
            if not include_expired:
                query = query.where(Session.expires_at > func.now())

            query = query.order_by(Session.created_at.desc())

            result = await session.execute(query)
            rows = result.all()

            return [
                ActiveSessionInfo(
                    id=row.id,
                    created_at=row.created_at,
                    expires_at=row.expires_at
                ) for row in rows
            ]

    @classmethod
    async def check_login_exist(cls, login: str) -> bool:
        async with new_session() as session:
            async with session.begin():
                login_check = await session.execute(
                    select(OrganizationUser.id).where(OrganizationUser.login == login)
                )

                return login_check.scalar_one_or_none() is not None

    @classmethod
    async def change_user_password(cls, user_id: int, password_hash: str) -> OrganizationUser | None:
        async with new_session() as session:
            user = await session.execute(
                select(OrganizationUser).where(OrganizationUser.id == user_id)
            )

            row = user.scalar_one_or_none()
            if row is None:
                return None

            row.password_hash = password_hash
            await session.commit()  # Коммитим изменения
            await session.refresh(row)
            return row

    @classmethod
    async def delete_organization_user(cls, user_id: int) -> bool:
        async with new_session() as session:
            async with session.begin():
                user = await session.get(OrganizationUser, user_id)
                if user is None:
                    return False

                await session.delete(user)
                return True

    @classmethod
    async def delete_organization_participants(cls, participant_id: int) -> bool:
        async with new_session() as session:
            async with session.begin():
                participant = await session.get(OrganizationParticipant, participant_id)
                if participant is None:
                    return False

                await session.delete(participant)
                return True

    @classmethod
    async def create_organization_user(
            cls,
            login: str,
            password_hash: str,
            email: str
    ) -> OrganizationUser | None:
        async with new_session() as session:
            async with session.begin():
                # Проверяем существование по login
                login_check = await session.execute(
                    select(OrganizationUser.id).where(OrganizationUser.login == login)
                )
                if login_check.scalar_one_or_none() is not None:
                    return None  # Логин уже занят

                # Проверяем существование по email
                email_check = await session.execute(
                    select(OrganizationUser.id).where(OrganizationUser.email == email)
                )
                if email_check.scalar_one_or_none() is not None:
                    return None  # Email уже занят

                # Создаем пользователя
                new_user = OrganizationUser(
                    login=login,
                    password_hash=password_hash,
                    email=email
                )

                session.add(new_user)
                await session.flush()
                await session.refresh(new_user)

                return new_user

    @classmethod
    async def add_new_organization(
            cls,
            organization_name: str,
            organization_description: str,
    ) -> Organization:
        async with new_session() as session:
            async with session.begin():
                new_organization = Organization(
                    name=organization_name,
                    description=organization_description
                )

                # Добавляем в сессию
                session.add(new_organization)
                await session.flush()  # Получаем ID созданной записи
                await session.refresh(new_organization)  # Обновляем объект из БД

                return new_organization

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
