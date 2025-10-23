import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pydantic import BaseModel, EmailStr
from typing import List
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Schema para enviar e-mails (mesma interface que você já usava)
class EmailSchema(BaseModel):
    email: List[EmailStr]      # lista de destinatários
    subject: str
    body: str                  # HTML

async def send_mail(email_data: EmailSchema):
    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        from_email = os.getenv("EMAIL_FROM", "no-reply@mathzombie.com")

        message = Mail(
            from_email=from_email,
            to_emails=email_data.email,
            subject=email_data.subject,
            html_content=email_data.body
        )
        response = sg.send(message)
        logger.info("E-mail enviado via SendGrid: status_code=%s", response.status_code)
        return {"message": f"E-mail enviado com sucesso para {email_data.email}!"}

    except Exception as e:
        logger.exception("Erro ao enviar e-mail via SendGrid")
        raise e
