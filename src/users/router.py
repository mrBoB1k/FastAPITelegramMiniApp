from fastapi import APIRouter, Depends, HTTPException, status

from users.schemas import UserRegister, TelegramId, UserRole, UsersChangeRole, UsersBase, UserRoleEnum
from typing import Annotated
from users.repository import Repository

from interactivities.repository import Repository as Repository_Interactivities
from interactivities.schemas import InteractiveCreate, Question, Answer, InteractiveType

from websocket.router import manager as ws_manager

router = APIRouter(
    prefix="/api/users",
    tags=["/api/users"]
)


@router.post("/register")
async def register(
        user: Annotated[UserRegister, Depends()],
) -> UserRole:
    user_role = await Repository.get_role_by_telegram_id(user.telegram_id)
    if user_role is None:
        if user.username is None:
            user.username = ""
        user_role = await Repository.register_user(user)
    return UserRole(role=user_role)


@router.get("/me/role")
async def get_me_role(
        data: Annotated[TelegramId, Depends()],
) -> UserRole:
    user_role = await Repository.get_role_by_telegram_id(data.telegram_id)
    if user_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRole(role=user_role)


@router.patch("/user_change_role")
async def change_role(
        data: Annotated[UsersChangeRole, Depends()],
) -> UsersBase:
    user_role = await Repository.get_role_by_telegram_id(data.telegram_id)
    if user_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_role == data.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User already has role")
    user = await Repository.change_role(data)

    if data.role == UserRoleEnum.leader:
        interactive_count = await Repository.get_interactive_count_by_user_id(user.id)
        if interactive_count == 0:
            code = await Repository_Interactivities.generate_unique_code()
            data_first_intractive.code = code
            data_first_intractive.created_by_id = user.id
            i = await Repository_Interactivities.create_interactive(data=data_first_intractive, images=None)
    return user


@router.delete("/{telegram_id}")
async def delete_interactive(
        telegram_id: Annotated[TelegramId, Depends()],
):
    user_id_role = await Repository_Interactivities.get_user_id_and_role_by_telegram_id(telegram_id.telegram_id)
    if user_id_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_id = user_id_role.user_id

    # удаление всех интерактивов вместе с ответами участников
    interactive_ids = await Repository.get_all_interactive_id(user_id)
    for interactive_id in interactive_ids:
        if interactive_id in ws_manager.interactive_sessions:
            await ws_manager.disconnect_delete(interactive_id=interactive_id)

        else:
            await Repository_Interactivities.remove_participant_from_interactive(interactive_id=interactive_id)

        new_interactive_id = await Repository_Interactivities.delite_interactive(interactive_id=interactive_id)
        if new_interactive_id.interactive_id != interactive_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"какая-то хуйня случилась с удалением интерактив {interactive_id}")

    # удаление всех участий в интерактивах
    quiz_participants_ids = await Repository.get_all_quiz_participants_id(user_id)
    for quiz_participant_id in quiz_participants_ids:
        flag = await Repository.delete_quiz_participant_and_answers(quiz_participant_id=quiz_participant_id)
        if not flag:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"какая-то хуйня случилась с удалением твоего участия в интерактиве с quiz_participant_id {quiz_participant_id}")

    # удаление пользователя
    flag = await Repository.delete_user(user_id=user_id)
    if not flag:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Ну какая-то хуйня пошла, и не смог удалить пользователя")

    return


data_first_intractive = InteractiveCreate(
    code="1131",
    created_by_id=1,
    title="«Маленький Квест Знаний»",
    description="Небольшой увлекательный тест, который проверит вашу наблюдательность, логическое мышление и знание известных фактов",
    target_audience="абитуриенты ВУЗа",
    location="Онлайн-вебинар \"Знаток\"",
    responsible_full_name="Иванов Иван Иванович",
    answer_duration=15,
    discussion_duration=10,
    countdown_duration=10,
    questions=[
        Question(
            text="Какое животное самое быстрое на суше?",
            position=1,
            type=InteractiveType.one,
            image="https://carclicker.ru/images/d997d3ba-51cc-463d-aad6-544f9c37ac67.webp",
            score=1,
            answers=[Answer(
                text="Лев",
                is_correct=False,
            ),
                Answer(
                    text="Гепард",
                    is_correct=True,
                ),
                Answer(
                    text="Лошадь",
                    is_correct=False,
                ),
                Answer(
                    text="Олень",
                    is_correct=False,
                )
            ]
        ),
        Question(
            text="Какой газ мы выдыхаем в большем количестве, чем вдыхаем?",
            position=2,
            type=InteractiveType.one,
            image="",
            score=1,
            answers=[Answer(
                text="Азот",
                is_correct=False,
            ),
                Answer(
                    text="Кислород",
                    is_correct=False,
                ),
                Answer(
                    text="Углекислый газ",
                    is_correct=True,
                ),
                Answer(
                    text="Водород",
                    is_correct=False,
                )
            ]
        ),
        Question(
            text="Какие из перечисленных фруктов растут на деревьях?",
            position=3,
            type=InteractiveType.many,
            image="https://carclicker.ru/images/12bb4bcf-5dc0-408e-a7c3-a9d6b9143b17.jpg",
            score=1,
            answers=[Answer(
                text="Банан",
                is_correct=False,
            ),
                Answer(
                    text="Яблоко",
                    is_correct=True,
                ),
                Answer(
                    text="Ананас",
                    is_correct=False,
                ),
                Answer(
                    text="Груша",
                    is_correct=True,
                ),
                Answer(
                    text="Арбуз",
                    is_correct=False,
                )
            ]
        ),
        Question(
            text="Что относится к устройствам ввода информации?",
            position=4,
            type=InteractiveType.many,
            image="",
            score=1,
            answers=[Answer(
                text="Монитор",
                is_correct=False,
            ),
                Answer(
                    text="Клавиатура",
                    is_correct=True,
                ),
                Answer(
                    text="Мышь",
                    is_correct=True,
                ),
                Answer(
                    text="Наушники",
                    is_correct=False,
                )
            ]
        ),
        Question(
            text="Как называется самая большая планета Солнечной системы?",
            position=5,
            type=InteractiveType.text,
            image="https://carclicker.ru/images/5057709f-4c41-4e85-a236-ed11bca482ca.jpg",
            score=1,
            answers=[Answer(
                text="Юпитер",
                is_correct=True,
            )
            ]
        ),
        Question(
            text="Как называется прибор, который измеряет температуру?",
            position=6,
            type=InteractiveType.text,
            image="",
            score=1,
            answers=[Answer(
                text="Термометр",
                is_correct=True,
            ),
                Answer(
                    text="Градусник",
                    is_correct=True,
                )
            ]
        )
    ]
)
