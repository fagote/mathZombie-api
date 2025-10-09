import os
from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv
import io

app = FastAPI()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    Recebe o CSV de um jogador, analisa os dados e retorna um diagnóstico detalhado
    sobre o desempenho individual.
    """
    if not file.filename.endswith(".csv"):
        return {"error": "Por favor, envie um arquivo CSV válido."}

    # Lê o CSV em memória
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))

    # Coleta dados básicos
    total_questoes = int(len(df))
    acertos = int(len(df[df["resultado"] == "certo"]))
    erros = int(len(df[df["resultado"] == "errado"]))
    taxa_acerto = float((acertos / total_questoes) * 100) if total_questoes else 0.0
    tempo_medio = float(df["tempo_resposta"].astype(float).mean()) if "tempo_resposta" in df else 0.0

    nome = str(df["nome"].iloc[0]) if "nome" in df else "Aluno desconhecido"
    idade = str(df["idade"].iloc[0]) if "idade" in df else "N/A"

    # Prepara um resumo numérico
    resumo_estatistico = f"""
    Nome: {nome}
    Idade: {idade}
    Total de questões: {total_questoes}
    Acertos: {acertos}
    Erros: {erros}
    Taxa de acerto: {taxa_acerto:.2f}%
    Tempo médio de resposta: {tempo_medio:.2f} segundos
    """

    # Converte tabela para texto (limita para evitar sobrecarga)
    tabela_texto = df.head(50).to_csv(index=False)

    # Prompt de diagnóstico individual
    prompt = f"""
    Você é um especialista em educação matemática com foco em avaliação diagnóstica.

    Abaixo estão os resultados de um aluno em um jogo de matemática.
    Use os dados para gerar um diagnóstico detalhado sobre o desempenho individual.

    Inclua:
    - Principais tipos de erro (ex: soma, subtração, multiplicação)
    - Dificuldades específicas (ex: operações com números grandes)
    - Observações sobre tempo de resposta
    - Sugestões pedagógicas para melhorar o aprendizado

    Dados gerais:
    {resumo_estatistico}

    Primeiras linhas da sessão (CSV):
    {tabela_texto}

    Gere um diagnóstico claro e pedagógico, em português, direcionado ao professor.
    """

    # Chama o Gemini
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)

    df["diagnostico"] = response.text  # adiciona o diagnóstico em uma coluna
    file_path_completo = os.path.join(UPLOAD_DIR, f"diagnostico_{file.filename}")
    df.to_csv(file_path_completo, index=False)

    return {
        "aluno": nome,
        "idade": idade,
        "questoes": total_questoes,
        "taxa_acerto": f"{taxa_acerto:.2f}%",
        "tempo_medio": f"{tempo_medio:.2f}s",
        "diagnostico": response.text
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

# como rodar a api: dentro da pasta api $ uvicorn main:app --reload
# como ativar ambiente virtual: source .venv/bin/activate