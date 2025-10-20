import os
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File
from dotenv import load_dotenv
import google.generativeai as genai
from sendEmail import send_mail, EmailSchema
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- CORS para permitir chamadas do GitHub Pages ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ideal depois: ["https://seuusuario.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configura Gemini ---
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Recebe o CSV, analisa e envia o diagnóstico por e-mail."""

    if not file.filename.endswith(".csv"):
        return {"error": "Por favor, envie um arquivo CSV válido."}

    # Lê o CSV diretamente da memória
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))

    # Extrai campos do CSV
    nome = str(df.get("nome", ["Aluno desconhecido"])[0])
    idade = str(df.get("idade", ["N/A"])[0])
    email = str(df.get("email", [None])[0])

    total_questoes = len(df)
    acertos = len(df[df["resultado"] == "certo"]) if "resultado" in df else 0
    erros = len(df[df["resultado"] == "errado"]) if "resultado" in df else 0
    taxa_acerto = (acertos / total_questoes * 100) if total_questoes else 0
    tempo_medio = (
        df["tempo_resposta"].astype(float).mean()
        if "tempo_resposta" in df
        else 0
    )

    resumo_estatistico = f"""
    Nome: {nome}
    Idade: {idade}
    Total de questões: {total_questoes}
    Acertos: {acertos}
    Erros: {erros}
    Taxa de acerto: {taxa_acerto:.2f}%
    Tempo médio de resposta: {tempo_medio:.2f} segundos
    """

    # Limita o CSV para o prompt
    tabela_texto = df.head(50).to_csv(index=False)

    # --- Prompt do Gemini ---
    prompt = f"""
    Você é um especialista em educação matemática com foco em avaliação diagnóstica.

    Abaixo estão os resultados de um aluno em um jogo de matemática.
    Gere um diagnóstico detalhado e pedagógico sobre o desempenho individual.

    Inclua:
    - Principais tipos de erro (ex: soma, subtração, multiplicação)
    - Dificuldades específicas (ex: operações com números grandes)
    - Observações sobre tempo de resposta
    - Sugestões pedagógicas para melhorar o aprendizado

    Dados gerais:
    {resumo_estatistico}

    Primeiras linhas da sessão (CSV):
    {tabela_texto}

    Escreva a resposta como um e-mail para o professor, em português formal e sem negritos.
    """

    # --- Chamada ao Gemini ---
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    diagnostico = response.text.strip()

    # --- Envio de e-mail ---
    mensagem = "E-mail do professor não encontrado no CSV."
    if email:
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
        await send_mail(email_data)
        mensagem = f"E-mail enviado com sucesso para {email}!"

    return {
        "aluno": nome,
        "idade": idade,
        "questoes": total_questoes,
        "taxa_acerto": f"{taxa_acerto:.2f}%",
        "tempo_medio": f"{tempo_medio:.2f}s",
        "diagnostico": diagnostico,
        "mensagem": mensagem
    }
