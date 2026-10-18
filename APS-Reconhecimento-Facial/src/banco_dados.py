import os
import psycopg
from pathlib import Path
from dotenv import load_dotenv

# Carrega as configurações do banco armazenadas no .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def conectar():
    # Abre uma conexão com o PostgreSQL
    return psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="aps_reconhecimento_facial",
        user="aps_user",
        password=os.environ["POSTGRES_PASSWORD"]
    )
