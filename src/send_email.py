from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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

    # отправка
    await aiosmtplib.send(
        message,
        hostname=smtp_server,
        port=port,
        username=login,
        password=password,
        use_tls=True,
    )

async def validate_receiver_email(email: str) -> str | None:
    try:
        valid = validate_email(email)
        return valid.email
    except EmailNotValidError as e:
        return None
