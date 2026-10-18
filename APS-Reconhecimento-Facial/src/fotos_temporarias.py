import atexit
import shutil
import tempfile
import uuid
from pathlib import Path

# Cria uma pasta temporária para armazenar as fotos capturadas
PASTA_FOTOS = Path(tempfile.mkdtemp(prefix="fotos_cadastro_"))

# Remove a pasta e suas fotos quando o programa terminar
atexit.register(shutil.rmtree, PASTA_FOTOS, ignore_errors=True)


def salvar_foto(conteudo):
    # Gera um identificador único para o arquivo da foto
    foto_id = str(uuid.uuid4())
    caminho = PASTA_FOTOS / f"{foto_id}.jpg"

    caminho.write_bytes(conteudo)
    return foto_id


def obter_caminho_foto(foto_id):
    # Verifica se o identificador possui um formato UUID válido
    try:
        foto_id = str(uuid.UUID(foto_id))
    except (ValueError, TypeError, AttributeError):
        return None

    caminho = PASTA_FOTOS / f"{foto_id}.jpg"

    # Retorna o caminho somente se o arquivo existir
    return caminho if caminho.is_file() else None
