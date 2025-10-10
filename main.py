import os
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File
from dotenv import load_dotenv
import google.generativeai as genai

from sendEmail import send_mail, EmailSchema  # importa a função de envio

app = FastAPI()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Carrega variáveis de ambiente e configura Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    Recebe o CSV de um jogador, analisa os dados e envia um diagnóstico
    detalhado por e-mail ao professor informado no próprio CSV.
    """
    if not file.filename.endswith(".csv"):
        return {"error": "Por favor, envie um arquivo CSV válido."}

    # Lê o CSV em memória
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))

    nome = str(df["nome"].iloc[0]) if "nome" in df else "Aluno desconhecido"
    idade = str(df["idade"].iloc[0]) if "idade" in df else "N/A"
    email = str(df["email"].iloc[0]) if "email" in df else None

    total_questoes = int(len(df))
    acertos = int(len(df[df["resultado"] == "certo"]))
    erros = int(len(df[df["resultado"] == "errado"]))
    taxa_acerto = float((acertos / total_questoes) * 100) if total_questoes else 0.0
    tempo_medio = float(df["tempo_resposta"].astype(float).mean()) if "tempo_resposta" in df else 0.0

    resumo_estatistico = f"""
    Nome: {nome}
    Idade: {idade}
    Total de questões: {total_questoes}
    Acertos: {acertos}
    Erros: {erros}
    Taxa de acerto: {taxa_acerto:.2f}%
    Tempo médio de resposta: {tempo_medio:.2f} segundos
    """

    # Limita as primeiras linhas do CSV (para não sobrecarregar o prompt)
    tabela_texto = df.head(50).to_csv(index=False)

    # ======= Prompt para o Gemini =======
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

    # ======= Gera diagnóstico com Gemini =======
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    diagnostico = response.text

    # ======= Salva CSV atualizado =======
    df["diagnostico"] = diagnostico
    file_path = os.path.join(UPLOAD_DIR, f"diagnostico_{file.filename}")
    df.to_csv(file_path, index=False)

    # ======= Envia e-mail ao professor =======
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
    else:
        mensagem = "E-mail do professor não encontrado no CSV."

    return {
        "aluno": nome,
        "idade": idade,
        "questoes": total_questoes,
        "taxa_acerto": f"{taxa_acerto:.2f}%",
        "tempo_medio": f"{tempo_medio:.2f}s",
        "diagnostico": diagnostico,
        "mensagem": mensagem
    }

@app.get("/list")
def list_csv():
    return {"files": os.listdir(UPLOAD_DIR)}

@app.get("/read/{filename}") 
def read_csv(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return {"error": "Arquivo não encontrado"}
    
    df = pd.read_csv(file_path)
    return {"filename": filename, "rows": len(df), "data": df.to_dict(orient="records")}
