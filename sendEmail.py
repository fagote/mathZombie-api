import os
import logging
from pydantic import BaseModel, EmailStr
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

# Carrega variáveis de ambiente (.env local ou Railway)
load_dotenv()

# Configura logs
logger = logging.getLogger(__name__)

# Modelo de dados para envio de e-mail
class EmailSchema(BaseModel):
    email: list[EmailStr]  # lista de destinatários
    subject: str
    body: str  # conteúdo em HTML

# Função assíncrona de envio
async def send_mail(email: EmailSchema):
    """
    Envia um e-mail usando o SendGrid.
    Compatível com FastAPI e execução assíncrona.
    """

    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
    EMAIL_FROM = os.getenv("EMAIL_FROM")

    if not SENDGRID_API_KEY or not EMAIL_FROM:
        logger.error("❌ Variáveis de ambiente SENDGRID_API_KEY ou EMAIL_FROM ausentes!")
        return

    message = Mail(
        from_email=EMAIL_FROM,
        to_emails=email.email,
        subject=email.subject,
        html_content=email.body,
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(
            f"✅ E-mail enviado com sucesso! Status: {response.status_code} | Para: {email.email}"
        )
    except Exception as e:
        logger.exception(f"❌ Erro ao enviar e-mail: {e}")
