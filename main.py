import os
import io
import time
import asyncio
import logging
import pandas as pd
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import google.generativeai as genai
from sendEmail import send_mail, EmailSchema
from fastapi.middleware.cors import CORSMiddleware

# Configuração de logging detalhada
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")

if not API_KEY:
    logger.warning("GOOGLE_API_KEY não definido nas variáveis de ambiente!")
if not SENDGRID_KEY:
    logger.warning("SENDGRID_API_KEY não definido nas variáveis de ambiente!")

genai.configure(api_key=API_KEY)

# Configuração da API FastAPI
app = FastAPI()

# CORS liberado (pode restringir ao domínio do jogo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    inicio = time.time()
    logger.info("Endpoint /upload-csv chamado")

    try:
        if not file.filename.endswith(".csv"):
            return JSONResponse(status_code=400, content={"error": "Por favor, envie um arquivo CSV válido."})

        contents = await file.read()
        logger.info("Arquivo recebido: %s (%d bytes)", file.filename, len(contents))

        try:
            df = pd.read_csv(io.BytesIO(contents), encoding="utf-8")
        except Exception as e:
            logger.exception("Erro ao ler CSV")
            return JSONResponse(status_code=400, content={"error": f"Erro ao ler CSV: {str(e)}"})

        # Extração dos dados
        nome = str(df["nome"].iloc[0]) if "nome" in df else "Aluno desconhecido"
        idade = str(df["idade"].iloc[0]) if "idade" in df else "N/A"
        email = str(df["email"].iloc[0]) if "email" in df else None

        total_questoes = len(df)
        acertos = len(df[df["resultado"] == "certo"]) if "resultado" in df else 0
        erros = len(df[df["resultado"] == "errado"]) if "resultado" in df else 0
        taxa_acerto = (acertos / total_questoes) * 100 if total_questoes else 0.0
        tempo_medio = df["tempo_resposta"].astype(float).mean() if "tempo_resposta" in df else 0.0

        resumo = (
            f"Nome: {nome}\n"
            f"Idade: {idade}\n"
            f"Total de questões: {total_questoes}\n"
            f"Acertos: {acertos}\n"
            f"Erros: {erros}\n"
            f"Taxa de acerto: {taxa_acerto:.2f}%\n"
            f"Tempo médio de resposta: {tempo_medio:.2f} segundos\n"
        )

        logger.info("Resumo gerado:\n%s", resumo)

        tabela_texto = df.head(30).to_csv(index=False)
        prompt = f"""
Você é um especialista em educação matemática com foco em avaliação diagnóstica.

Dados gerais:
{resumo}

Primeiras linhas do CSV:
{tabela_texto}

Escreva um diagnóstico formal em português, no formato de e-mail para o professor.
"""

        # Gera diagnóstico em background
        async def gerar_diagnostico():
            logger.info("Chamando Gemini para gerar diagnóstico...")
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text.strip()

        try:
            diagnostico = await gerar_diagnostico()
            logger.info("Diagnóstico gerado com sucesso (%d caracteres)", len(diagnostico))
        except Exception as e:
            logger.exception("Erro no Gemini")
            return JSONResponse(status_code=500, content={"error": f"Erro ao gerar diagnóstico: {str(e)}"})

        # Envia e-mail em thread separada
        if email:
            logger.info("Iniciando envio de e-mail para %s", email)
            email_data = EmailSchema(
                email=[email],
                subject=f"Diagnóstico MathZombie - {nome}",
                body=f"""
                <h2>Diagnóstico do aluno {nome}</h2>
                <p>{diagnostico}</p>
                <hr>
                <p><strong>Resumo:</strong><br>{resumo}</p>
                """
            )
            asyncio.create_task(send_mail(email_data))  # dispara sem travar o worker

        tempo_total = time.time() - inicio
        logger.info("Tempo total de execução: %.2fs", tempo_total)

        return JSONResponse(content={
            "aluno": nome,
            "idade": idade,
            "questoes": total_questoes,
            "taxa_acerto": f"{taxa_acerto:.2f}%",
            "tempo_medio": f"{tempo_medio:.2f}s",
            "diagnostico": diagnostico,
            "email_enviado": bool(email),
            "tempo_execucao": round(tempo_total, 2)
        })

    except Exception as e:
        logger.exception("Erro inesperado no endpoint /upload-csv")
        return JSONResponse(status_code=500, content={"error": f"Erro interno: {str(e)}"})
