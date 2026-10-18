import base64
import logging
import time
from pathlib import Path
import cv2
import psycopg
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from camera_compartilhada import (
    obter_frame_atual,
    iniciar_camera,
    parar_camera,
    camera_ativa,
)
from estado import obter_estado
from fotos_temporarias import obter_caminho_foto, salvar_foto
from reconhecimento import reconhecer_imagem
from servicos import consultar_dados
from sessoes import criar_sessao, obter_sessao, encerrar_sessao
from usuarios import cadastrar_usuario, buscar_usuario_por_id


logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Reconhecimento Facial",
    version="1.1.0",
)

seguranca = HTTPBearer(auto_error=False)

TAMANHO_MAXIMO_IMAGEM = 5 * 1024 * 1024
TIPOS_IMAGEM_PERMITIDOS = {"image/jpeg", "image/png"}

BASE_DIR = Path(__file__).resolve().parent.parent


@app.get("/", include_in_schema=False)
def servir_frontend():
    caminho = BASE_DIR / "index.html"

    if not caminho.is_file():
        raise HTTPException(
            status_code=500,
            detail="Frontend index.html não encontrado.",
        )

    return FileResponse(caminho, media_type="text/html")


def obter_token(
    credenciais: HTTPAuthorizationCredentials | None = Depends(seguranca),
):
    if credenciais is None:
        raise HTTPException(
            status_code=401,
            detail="Token de autenticação não informado.",
        )

    return credenciais.credentials


def obter_frame_webcam():
    frame = obter_frame_atual()

    if frame is None:
        raise HTTPException(
            status_code=503,
            detail="A webcam ainda não disponibilizou uma imagem.",
        )

    return frame


@app.post("/camera/iniciar")
def iniciar_camera_api():
    try:
        iniciar_camera()
    except RuntimeError as erro:
        raise HTTPException(
            status_code=503,
            detail=str(erro),
        ) from erro

    return {
        "sucesso": True,
        "mensagem": "Câmera iniciada.",
    }


@app.post("/camera/parar")
def parar_camera_api():
    parar_camera()

    return {
        "sucesso": True,
        "mensagem": "Câmera encerrada.",
    }


def gerar_stream_camera():
    while camera_ativa():
        frame = obter_frame_atual()

        if frame is None:
            time.sleep(0.05)
            continue

        sucesso, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 60]
        )

        if sucesso:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )

        time.sleep(0.067)

@app.get("/camera/stream")
def stream_camera():
    if not camera_ativa():
        raise HTTPException(
            status_code=409,
            detail="A câmera não está iniciada.",
        )

    return StreamingResponse(
        gerar_stream_camera(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


# --------------------------------------------------
# CADASTRO DE USUÁRIOS
# --------------------------------------------------

@app.post("/usuarios", status_code=201)
async def cadastrar_usuario_api(
    cpf: str = Form(...),
    nome: str = Form(...),
    nivel_acesso: int = Form(...),
    imagem: UploadFile = File(...),
):
    cpf = cpf.strip()
    nome = nome.strip()

    try:
        if imagem.content_type not in TIPOS_IMAGEM_PERMITIDOS:
            raise HTTPException(
                status_code=400,
                detail="Envie uma imagem JPEG ou PNG.",
            )

        conteudo_imagem = await imagem.read(
            TAMANHO_MAXIMO_IMAGEM + 1
        )

        if not conteudo_imagem:
            raise HTTPException(
                status_code=400,
                detail="A imagem enviada está vazia.",
            )

        if len(conteudo_imagem) > TAMANHO_MAXIMO_IMAGEM:
            raise HTTPException(
                status_code=413,
                detail="A imagem não pode ultrapassar 5 MB.",
            )

        id_usuario = cadastrar_usuario(
            cpf=cpf,
            nome=nome,
            nivel_acesso=nivel_acesso,
            caminho_imagem=f"BYTEA:{cpf}",
            imagem=conteudo_imagem,
        )

    except HTTPException:
        raise

    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro),
        ) from erro

    except psycopg.errors.UniqueViolation as erro:
        raise HTTPException(
            status_code=409,
            detail="Já existe um usuário cadastrado com esse CPF.",
        ) from erro

    except psycopg.Error as erro:
        logger.exception("Falha ao cadastrar usuário.")
        raise HTTPException(
            status_code=503,
            detail="Não foi possível cadastrar o usuário no momento.",
        ) from erro

    finally:
        await imagem.close()

    return {
        "sucesso": True,
        "mensagem": "Usuário cadastrado com sucesso.",
        "id": id_usuario,
        "cpf": cpf,
        "nome": nome,
        "nivel_acesso": nivel_acesso,
    }


@app.post("/cadastro/foto")
def tirar_foto_cadastro():
    frame = obter_frame_webcam()

    sucesso, imagem_codificada = cv2.imencode(".jpg", frame)

    if not sucesso:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível codificar a foto.",
        )

    foto_id = salvar_foto(imagem_codificada.tobytes())

    return {
        "sucesso": True,
        "mensagem": "Foto capturada e armazenada temporariamente.",
        "foto_id": foto_id,
        "url_imagem": f"/cadastro/foto/{foto_id}",
    }


@app.get("/cadastro/foto/{foto_id}", include_in_schema=False)
def consultar_foto_cadastro(foto_id: str):
    caminho = obter_caminho_foto(foto_id)

    if caminho is None:
        raise HTTPException(
            status_code=404,
            detail="Foto temporária não encontrada ou expirada.",
        )

    return FileResponse(
        caminho,
        media_type="image/jpeg",
        filename="captura.jpg",
    )


# --------------------------------------------------
# RECONHECIMENTO FACIAL
# --------------------------------------------------

@app.post("/reconhecimento")
def reconhecer_usuario_api():
    frame = obter_frame_webcam()

    sucesso, imagem_codificada = cv2.imencode(".jpg", frame)

    if not sucesso:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível codificar a imagem do reconhecimento.",
        )

    foto_id = salvar_foto(imagem_codificada.tobytes())
    url_imagem = f"/cadastro/foto/{foto_id}"

    try:
        resultado = reconhecer_imagem(frame)

    except Exception as erro:
        logger.exception("Falha ao realizar reconhecimento facial.")
        raise HTTPException(
            status_code=503,
            detail="Não foi possível realizar o reconhecimento.",
        ) from erro

    return {
        "sucesso": True,
        "autenticado": resultado["autenticado"],
        "mensagem": resultado["mensagem"],
        "usuario": resultado.get("usuario"),
        "nivel_acesso": resultado.get("nivel_acesso"),
        "distancia": resultado.get("distancia"),
        "url_imagem": url_imagem,
    }


# --------------------------------------------------
# SESSÃO E DADOS DO USUÁRIO
# --------------------------------------------------

@app.get("/status")
def status_reconhecimento(token: str = Depends(obter_token)):
    sessao = obter_sessao(token)

    if sessao is None:
        raise HTTPException(
            status_code=401,
            detail="Sessão inválida ou expirada. Autentique-se novamente.",
        )

    usuario = buscar_usuario_por_id(sessao["id_usuario"])

    if usuario is None:
        raise HTTPException(
            status_code=404,
            detail="Usuário da sessão não encontrado ou inativo.",
        )

    id_usuario, cpf, nome, nivel_acesso, imagem = usuario

    if not imagem:
        raise HTTPException(
            status_code=404,
            detail="O usuário não possui uma foto cadastrada.",
        )

    imagem = bytes(imagem)

    if imagem.startswith(b"\xff\xd8\xff"):
        tipo_imagem = "image/jpeg"
    elif imagem.startswith(b"\x89PNG\r\n\x1a\n"):
        tipo_imagem = "image/png"
    else:
        raise HTTPException(
            status_code=500,
            detail="O formato da imagem cadastrada não é válido.",
        )

    imagem_base64 = base64.b64encode(imagem).decode("utf-8")

    return {
        "sucesso": True,
        "usuario": nome,
        "cpf": cpf,
        "nivel_acesso": nivel_acesso,
        "foto": imagem_base64,
        "tipo_imagem": tipo_imagem,
    }


@app.post("/sessao")
def iniciar_sessao():
    estado = obter_estado()

    if not estado["autenticado"] or estado["id_usuario"] is None:
        raise HTTPException(
            status_code=401,
            detail="Nenhum usuário reconhecido recentemente pela câmera.",
        )

    token = criar_sessao(
        id_usuario=estado["id_usuario"],
        usuario=estado["usuario"],
        nivel_acesso=estado["nivel_acesso"],
    )

    return {
        "sucesso": True,
        "mensagem": "Sessão iniciada.",
        "token": token,
        "tipo": "Bearer",
        "expiracao_inatividade_segundos": 900,
        "usuario": estado["usuario"],
        "nivel_acesso": estado["nivel_acesso"],
    }


@app.delete("/sessao")
def finalizar_sessao(token: str = Depends(obter_token)):
    encerrar_sessao(token)

    return {
        "sucesso": True,
        "mensagem": "Sessão encerrada.",
    }


@app.get("/dados/{nivel_recurso}")
def obter_dados_ambientais(
    nivel_recurso: int,
    token: str = Depends(obter_token),
):
    sessao = obter_sessao(token)

    if sessao is None:
        raise HTTPException(
            status_code=401,
            detail="Sessão inválida ou expirada. Autentique-se novamente.",
        )

    resultado = consultar_dados(
        nome=sessao["usuario"],
        nivel_usuario=sessao["nivel_acesso"],
        nivel_recurso=nivel_recurso,
    )

    if not resultado["sucesso"]:
        mensagem = resultado["mensagem"]

        status_por_mensagem = {
            "Acesso negado.": 403,
            "Não foi possível consultar os dados no momento.": 503,
        }

        raise HTTPException(
            status_code=status_por_mensagem.get(mensagem, 400),
            detail=mensagem,
        )

    return resultado
