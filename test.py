import os
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega o .env
load_dotenv()

# Configura a API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Lista os modelos disponíveis
for m in genai.list_models():
    print(m.name)
