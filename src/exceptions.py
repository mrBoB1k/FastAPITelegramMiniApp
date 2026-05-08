from fastapi import HTTPException, status, WebSocketException


### временная поддержка SECRET_KEY
class XKeyInvalidException(HTTPException):
    """Не правильный x_key передали на вход"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "X-Key header invalid",
                "code": "X_KEY_INVALID",
            }
        )


### АВТОРИЗАЦИЯ
class CredentialsException(HTTPException):
    """Ошибка валидаций access token"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Could not validate credentials",
                "code": "INVALID_ACCESS_TOKEN",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


class InactiveUserException(HTTPException):
    """У пользователя поменялась роль"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Inactive user",
                "code": "INACTIVE_USER",
            },
        )


class IncorrectUserDataException(HTTPException):
    """Не правильные входные данные"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Incorrect username or password",
                "code": "INVALID_CREDENTIALS",
            },
        )


class MissingRefreshTokenException(HTTPException):
    """Нету refresh token"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Missing refresh token",
                "code": "MISSING_REFRESH_TOKEN",
            },
        )


class InvalidRefreshTokenException(HTTPException):
    """Не правильный/невалидный refresh token"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Invalid refresh token",
                "code": "INVALID_REFRESH_TOKEN",
            },
        )

class LeaderCannotAddNewUserException(HTTPException):
    """Пользователь с ролью leader не может добавлять участников в организацию"""

    def __init__(self):
        super().__init__(
            status_code=403,
            detail={
                "message": "Only admin and organizer can add participants in organization",
                "code": "LEADER_CANNOT_ADD_NEW_USER",
            },
        )

class CannotAddUserAnotherOrganizationException(HTTPException):
    """Нельзя добавить людей из других организаций"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "You cannot add a user who is a member of another organization.",
                "code": "CANNOT_ADD_USER_ANOTHER_ORGANIZATION",
            },
        )

class InvalidEmailException(HTTPException):
    """Не правильный формат email"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Email is invalid",
                "code": "INVALID_EMAIL",
            },
        )

class InvalidLoginException(HTTPException):
    """Не правильный формат login"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Login is invalid",
                "code": "INVALID_LOGIN",
            },
        )


class InvalidPasswordException(HTTPException):
    """Не правильный формат password"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Password is invalid",
                "code": "INVALID_PASSWORD",
            },
        )

class EmailSendException(HTTPException):
    """Ошибка при отправке письма на сервере"""

    def __init__(self):
        super().__init__(
            status_code=500,
            detail={
                "message": "There was an error sending the email",
                "code": "EMAIL_SEND",
            },
        )

### ОРГАНИЗАЦИЯ
class OrganizationNotFoundException(HTTPException):
    """Не найдена организация"""

    def __init__(self):
        super().__init__(
            status_code=404,
            detail={
                "message": "Organization not found",
                "code": "ORGANIZATION_NOT_FOUND",
            },
        )


class NameTooLongException(HTTPException):
    """Слишком длинное/короткое имя"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Name too long (name must be between 3 and 32 characters)",
                "code": "NAME_TOO_LONG",
            },
        )


class OrganizationNameTooLongException(HTTPException):
    """Слишком длинное/короткое имя для организаций"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Organization name too long (Organization_name must be between 3 and 32 characters)",
                "code": "ORGANIZATION_NAME_TOO_LONG",
            },
        )


class OrganizationDescriptionTooLongException(HTTPException):
    """Слишком длинное/короткое описание для организаций"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Organization description too long (organization_description must be between 0 and 200 characters)",
                "code": "ORGANIZATION_DESCRIPTION_TOO_LONG",
            },
        )


class OnlyOrganizerCanChangeDescriptionException(HTTPException):
    """Только пользователь с ролью организатор может поменять описание организаций"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Only organizer can change description",
                "code": "ONLY_ORGANIZER_CAN_CHANGE_DESCRIPTION",
            },
        )


class UserNotFoundInOrganizationException(HTTPException):
    """Не найден пользователь, которому хотят поменять роль"""

    def __init__(self):
        super().__init__(
            status_code=404,
            detail={
                "message": "User_to not found on organization",
                "code": "USER_NOT_FOUND_IN_ORGANIZATION",
            },
        )


class UsersInDifferentOrganizationException(HTTPException):
    """Пользователь, которому хотят роль, находится в другой организаций"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "User_from and User_to are in different organizations",
                "code": "USERS_IN_DIFFERENT_ORGANIZATIONS",
            },
        )


class CannotChangeOwnRoleException(HTTPException):
    """Пользователь не может поменять свою роль"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "You cannot change your own role",
                "code": "CANNOT_CHANGE_OWN_ROLE",
            },
        )


class InsufficientRolePermissionsToChangeRoleException(HTTPException):
    """Только пользователи с роль админ и организатор могут менять роль"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Only admin and organizer can change role",
                "code": "INSUFFICIENT_ROLE_PERMISSIONS_TO_CHANGE_ROLE",
            },
        )


class AdminCanOnlyChangeLeaderException(HTTPException):
    """Админ может поменять роль только пользователю с ролью лидер"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Admin can only change the leader role",
                "code": "ADMIN_CAN_ONLY_CHANGE_LEADER",
            },
        )


### Интерактив
class InteractiveParsingException(HTTPException):
    """Проблема с парсом в нужный формат данных об интерактиве"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Problem with parsing interactive",
                "code": "INTERACTIVE_PARSING_ERROR",
            },
        )


class InvalidQuestionPositionsException(HTTPException):
    """Вопросы в интерактиве должны начинаться с 1"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Question positions must be sequential starting from 1",
                "code": "INVALID_QUESTION_POSITIONS",
            },
        )


class InvalidQuestionScoreException(HTTPException):
    """Баллы за вопрос могут быть от 1 до 5 только"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Question score must be between 1 and 5",
                "code": "INVALID_QUESTION_SCORE",
            },
        )


class TooManyAnswersException(HTTPException):
    """Слишком много вариантов ответа у вопроса"""

    def __init__(self, question_text: str, question_type: str):
        super().__init__(
            status_code=400,
            detail={
                "message": f"Too many answers for question {question_text} of type {question_type}",
                "code": "TOO_MANY_ANSWERS",
            },
        )


class RequiresOneCorrectAnswerException(HTTPException):
    """На вопросе типа one больше 1 правильного ответа"""

    def __init__(self, question_text: str, question_type: str):
        super().__init__(
            status_code=400,
            detail={
                "message": f"There must be one correct answer in a question {question_text} of type {question_type}.",
                "code": "REQUIRES_ONE_CORRECT_ANSWER",
            },
        )


class RequiresManyCorrectAnswerException(HTTPException):
    """На вопросе типа many должно быть несколько правильных ответов"""

    def __init__(self, question_text: str, question_type: str):
        super().__init__(
            status_code=400,
            detail={
                "message": f"A question {question_text} of type {question_type} must have more than one correct answer.",
                "code": "REQUIRES_MANY_CORRECT_ANSWERS",
            },
        )


class RequiresTextCorrectAnswerException(HTTPException):
    """На вопросе типа text все ответы должны быть правильными"""

    def __init__(self, question_text: str, question_type: str):
        super().__init__(
            status_code=400,
            detail={
                "message": f"A question {question_text} of type {question_type} all answers must be correct",
                "code": "REQUIRES_TEXT_CORRECT_ANSWERS",
            },
        )


class InsufficientImageException(HTTPException):
    """Получено не достаточно изображений для интерактива"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "fewer images were received than expected",
                "code": "INSUFFICIENT_IMAGES",
            },
        )


class FileSizeExceededException(HTTPException):
    """Размер файла должен быть до 5 мб"""

    def __init__(self):
        super().__init__(
            status_code=413,
            detail={
                "message": "File size exceeds 5 MB limit",
                "code": "FILE_SIZE_EXCEEDED",
            },
        )


class InvalidContentTypeException(HTTPException):
    """Не поддерживаемый тип изображения"""

    def __init__(self, content_type: str):
        super().__init__(
            status_code=415,
            detail={
                "message": f"Invalid content type: {content_type}. Only images are allowed.",
                "code": "INVALID_CONTENT_TYPE",
            },
        )


class InvalidRangeNumbersException(HTTPException):
    """Не правильные входные данные для получения списка(число от и число до)"""

    def __init__(self, from_number: int, to_number: int):
        super().__init__(
            status_code=400,
            detail={
                "message": f"Invalid input data: from_number {from_number} and to_number {to_number} are invalid",
                "code": "INVALID_RANGE_NUMBERS",
            },
        )


class InteractiveNotFoundException(HTTPException):
    """Интерактив не найден"""

    def __init__(self):
        super().__init__(
            status_code=404,
            detail={
                "message": "Interactive not found",
                "code": "INTERACTIVE_NOT_FOUND",
            },
        )


class InteractiveAlreadyStartedException(HTTPException):
    """Интерактив запущен"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Interactive started",
                "code": "INTERACTIVE_ALREADY_STARTED",
            },
        )


class InteractiveAlreadyEndException(HTTPException):
    """Интерактив завершён"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "Interactive already end",
                "code": "INTERACTIVE_ALREADY_END",
            },
        )


class LeaderCannotDeleteForeignInteractiveException(HTTPException):
    """Пользователь с ролью leader не может удалять интерактивы других людей"""

    def __init__(self):
        super().__init__(
            status_code=403,
            detail={
                "message": "Leader cannot delete interactive other people",
                "code": "LEADER_CANNOT_DELETE_FOREIGN_INTERACTIVE",
            },
        )


class CannotDeleteForeignOrganizationInteractiveException(HTTPException):
    """Пользователь не может удалять интерактивы других организаций"""

    def __init__(self):
        super().__init__(
            status_code=403,
            detail={
                "message": "You cannot delete interactive other organization",
                "code": "CANNOT_DELETE_FOREIGN_ORGANIZATION_INTERACTIVE",
            },
        )


class CannotAccessForeignOrganizationInteractiveException(HTTPException):
    """Нельзя получить информацию об интерактиве другой организаций"""

    def __init__(self):
        super().__init__(
            status_code=403,
            detail={
                "message": "You cannot get interactive other organization",
                "code": "CANNOT_ACCESS_FOREIGN_ORGANIZATION_INTERACTIVE",
            },
        )

### Reports

class InteractiveNotConductedException(HTTPException):
    """Интерактив не завершён или принадлежит не вашей организаций"""

    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "message": "interactive not found on organization, or not conducted",
                "code": "INTERACTIVE_NOT_CONDUCTED",
            },
        )

### MinIO

class BucketCreationFailedException(HTTPException):
    """Проблема с созданием бакета"""

    def __init__(self, exc: str):
        super().__init__(
            status_code=500,
            detail={
                "message": f"Error creating bucket: {exc}",
                "code": "BUCKET_CREATION_FAILED",
            },
        )


class FileUploadFailedException(HTTPException):
    """Проблема с загрузкой изображений в бакет"""

    def __init__(self, exc: str):
        super().__init__(
            status_code=500,
            detail={
                "message": f"Error uploading file: {exc}",
                "code": "FILE_UPLOAD_FAILED",
            },
        )


### Вебсокет
class WebSocketError(WebSocketException):
    """Базовый класс для всех WebSocket ошибок"""

    def __init__(self, code: int, detail: dict):
        # Преобразуем dict в строку для reason
        import json
        super().__init__(code=code, reason=json.dumps(detail, ensure_ascii=False))


class InteractiveNotFoundWSException(WebSocketError):
    """Интерактив не найден"""

    def __init__(self):
        super().__init__(
            code=4000,
            detail={
                "message": "Interactive not found",
                "code": "INTERACTIVE_NOT_FOUND"
            }
        )


class InteractiveAlreadyEndWSException(WebSocketError):
    """Интерактив уже закончен"""

    def __init__(self):
        super().__init__(
            code=4001,
            detail={
                "message": "Interactive already end",
                "code": "INTERACTIVE_ALREADY_END"
            }
        )


class UserNotFoundWSException(WebSocketError):
    """Пользователь не найден"""

    def __init__(self):
        super().__init__(
            code=4002,
            detail={
                "message": "User not found",
                "code": "USER_NOT_FOUND"
            }
        )


class UserAccessDeniedWSException(WebSocketError):
    """Пользователь не имеет прав запустить интерактив"""

    def __init__(self):
        super().__init__(
            code=4003,
            detail={
                "message": "User does not have access",
                "code": "USER_ACCESS_DENIED"
            }
        )


class InteractiveRunningNowWSException(WebSocketError):
    """Интерактив уже запущен"""

    def __init__(self):
        super().__init__(
            code=4004,
            detail={
                "message": "Interactive running now",
                "code": "INTERACTIVE_RUNNING_NOW"
            }
        )


class CredentialsWSException(WebSocketError):
    """Ошибка валидаций access token (для вебсокета)"""

    def __init__(self):
        super().__init__(
            code=status.WS_1008_POLICY_VIOLATION,
            detail={
                "message": "Could not validate credentials",
                "code": "INVALID_ACCESS_TOKEN"
            }
        )


class InactiveUserWSException(WebSocketError):
    """У пользователя поменялась роль (для вебсокета)"""

    def __init__(self):
        super().__init__(
            code=status.WS_1008_POLICY_VIOLATION,
            detail={
                "message": "Inactive user",
                "code": "INACTIVE_USER"
            }
        )

class YouBeenRemoveWSException(WebSocketError):
    """Пользователь задал слишком длинное имя"""

    def __init__(self):
        super().__init__(
            code=4005,
            detail={
                "message": "You have been removed from the interactive",
                "code": "YOU_BEEN_REMOVED"
            }
        )

class NameIsTooLongWSException(WebSocketError):
    """Пользователь задал слишком длинное имя"""

    def __init__(self):
        super().__init__(
            code=4006,
            detail={
                "message": "Name is too long/short",
                "code": "NAME_IS_TOO_LONG"
            }
        )
