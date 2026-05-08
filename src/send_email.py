from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import aiosmtplib
from email_validator import validate_email, EmailNotValidError

from config import EMAIL_PASSWORD, EMAIL_LOGIN, EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT

async def send_email(receiver_email: str, subject: str, body: str):
    smtp_server = EMAIL_SMTP_SERVER
    port = EMAIL_SMTP_PORT

    login = EMAIL_LOGIN
    password = EMAIL_PASSWORD

    sender_email = login

    # создаём письмо
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))
    try:
        # отправка
        await aiosmtplib.send(
            message,
            hostname=smtp_server,
            port=port,
            username=login,
            password=password,
            use_tls=True,
        )
    except Exception as e:
        print(e)

async def send_email_with_file(
    receiver_email: str,
    subject: str,
    body: str,
    file: bytes | None = None,
    filename: str | None = None,
):
    message = MIMEMultipart()
    message["From"] = EMAIL_LOGIN
    message["To"] = receiver_email
    message["Subject"] = subject

    # текст письма
    message.attach(MIMEText(body or "", "plain"))

    # если есть файл — добавляем
    if file and filename:
        part = MIMEApplication(file)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"'
        )
        message.attach(part)

    await aiosmtplib.send(
        message,
        hostname=EMAIL_SMTP_SERVER,
        port=EMAIL_SMTP_PORT,
        username=EMAIL_LOGIN,
        password=EMAIL_PASSWORD,
        use_tls=True,
    )


async def validate_receiver_email(email: str) -> str | None:
    try:
        valid = validate_email(email)
        return valid.email
    except EmailNotValidError as e:
        return None
