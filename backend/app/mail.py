import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def send_email(recipient: str, subject: str, body: str) -> None:
    host = current_app.config.get("MAIL_HOST")
    sender = current_app.config.get("MAIL_FROM")
    if not host or not sender:
        if current_app.config.get("TESTING") or (
            current_app.config.get("APP_ENV") != "production"
        ):
            current_app.logger.info(
                "Development email to %s: %s\n%s", recipient, subject, body
            )
            return
        raise RuntimeError("Production email delivery is not configured.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    port = int(current_app.config.get("MAIL_PORT", 587))
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.ehlo()
        if current_app.config.get("MAIL_USE_TLS", True):
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(message)
