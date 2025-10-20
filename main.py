import os
import io
import logging
import pandas as pd
from fastapi import FastAPI, UploadFile, File
from dotenv import load_dotenv
import google.generativeai as genai
from sendEmail import send_mail, EmailSchema
from fastapi.middleware.cors import CORSMiddleware

# Logging detalhado pra aparecer nos logs do Railway
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY não definido nas variáveis de ambiente!")

genai.configure(api_key=API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # no futuro, limite ao seu domínio do GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    logger.info("Endpoint /upload-csv chamado")
    try:
        if not file.filename.endswith(".csv"):
            logger.warning("Arquivo enviado não é CSV: %s", file.filename)
            return {"error": "Por favor, envie um arquivo CSV válido."}

        contents = await file.read()
        logger.debug("Tamanho do arquivo recebido (bytes): %d", len(contents))

        try:
            df = pd.read_csv(io.BytesIO(contents))
        except Exception as e:
            logger.exception("Erro ao ler CSV com pandas")
            return {"error": f"Erro ao ler CSV: {str(e)}"}

        # Extrai campos
        nome = str(df["nome"].iloc[0]) if "nome" in df else "Aluno desconhecido"
        idade = str(df["idade"].iloc[0]) if "idade" in df else "N/A"
        email = str(df["email"].iloc[0]) if "email" in df else None

        total_questoes = int(len(df))
        acertos = int(len(df[df["resultado"] == "certo"])) if "resultado" in df else 0
        erros = int(len(df[df["resultado"] == "errado"])) if "resultado" in df else 0
        taxa_acerto = float((acertos / total_questoes) * 100) if total_questoes else 0.0
        tempo_medio = float(df["tempo_resposta"].astype(float).mean()) if "tempo_resposta" in df else 0.0

        resumo_estatistico = (
            f"Nome: {nome}\n"
            f"Idade: {idade}\n"
            f"Total de questões: {total_questoes}\n"
            f"Acertos: {acertos}\n"
            f"Erros: {erros}\n"
            f"Taxa de acerto: {taxa_acerto:.2f}%\n"
            f"Tempo médio de resposta: {tempo_medio:.2f} segundos\n"
        )

        tabela_texto = df.head(50).to_csv(index=False)

        prompt = f"""
Você é um especialista em educação matemática com foco em avaliação diagnóstica.

Dados gerais:
{resumo_estatistico}

Primeiras linhas da sessão (CSV):
{tabela_texto}

Escreva a resposta como um e-mail para o professor, em português formal e sem negritos.
"""

        logger.info("Chamando Gemini para gerar diagnóstico...")
        try:
            model = genai.GenerativeModel("models/gemini-2.5-flash")
            response = model.generate_content(prompt)
            diagnostico = response.text.strip()
            logger.info("Gemini retornou com sucesso (tamanho diagnóstico: %d)", len(diagnostico))
        except Exception as e:
            logger.exception("Erro durante chamada ao Gemini")
            return {"error": f"Erro na geração do diagnóstico: {str(e)}"}

        # Envia e-mail (não salva arquivo no disco)
        mensagem = "E-mail do professor não encontrado no CSV."
        if email:
            logger.info("Preparando e-mail para %s", email)
            email_data = EmailSchema(
                email=[email],
                subject=f"Diagnóstico MathZombie - {nome}",
                body=f"""
                <h2>Diagnóstico do aluno {nome}</h2>
                <p>{diagnostico}</p>
                <hr>
                <p><strong>Resumo:</strong><br>{resumo_estatistico}</p>
                """
            )
            try:
                await send_mail(email_data)
                mensagem = f"E-mail enviado com sucesso para {email}!"
                logger.info("E-mail enviado com sucesso para %s", email)
            except Exception as e:
                logger.exception("Erro ao enviar e-mail")
                return {"error": f"Erro ao enviar e-mail: {str(e)}"}

        return {
            "aluno": nome,
            "idade": idade,
            "questoes": total_questoes,
            "taxa_acerto": f"{taxa_acerto:.2f}%",
            "tempo_medio": f"{tempo_medio:.2f}s",
            "diagnostico": diagnostico,
            "mensagem": mensagem
        }

    except Exception as e:
        logger.exception("Erro não esperado no endpoint /upload-csv")
        return {"error": f"Erro interno: {str(e)}"}
