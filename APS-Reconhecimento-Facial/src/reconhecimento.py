from deepface import DeepFace
from pathlib import Path
from threading import Lock
import logging
import tempfile
import cv2

from usuarios import listar_imagens_usuarios
from estado import atualizar_estado

logger = logging.getLogger(__name__)

LIMITE_DISTANCIA = 0.55
reconhecimento_lock = Lock()


def reconhecer_imagem(frame):
    # Evita executar dois reconhecimentos simultaneamente
    with reconhecimento_lock:
        try:
            usuarios = listar_imagens_usuarios()

            # Relaciona o ID de cada usuário aos seus dados
            usuarios_por_id = {
                str(usuario_id): (usuario_id, cpf, nome, nivel)
                for usuario_id, cpf, nome, nivel, imagem in usuarios
                if imagem
            }

            if not usuarios_por_id:
                atualizar_estado()
                return {
                    "autenticado": False,
                    "mensagem": "Nenhum usuário possui imagem cadastrada."
                }

            # Cria arquivos temporários para o DeepFace comparar as imagens
            with tempfile.TemporaryDirectory() as temp_dir:
                pasta_temp = Path(temp_dir)
                pasta_referencias = pasta_temp / "referencias"
                pasta_referencias.mkdir()

                for usuario_id, cpf, nome, nivel, imagem in usuarios:
                    if imagem:
                        caminho = pasta_referencias / f"{usuario_id}.jpg"
                        caminho.write_bytes(imagem)

                caminho_frame = pasta_temp / "captura.jpg"

                if not cv2.imwrite(str(caminho_frame), frame):
                    raise RuntimeError(
                        "Não foi possível salvar o frame temporário."
                    )

                # Compara o rosto capturado com as imagens cadastradas
                resultados = DeepFace.find(
                    img_path=str(caminho_frame),
                    db_path=str(pasta_referencias),
                    detector_backend="opencv",
                    enforce_detection=True
                )

                if not resultados or resultados[0].empty:
                    atualizar_estado()
                    return {
                        "autenticado": False,
                        "mensagem": "Nenhuma correspondência encontrada."
                    }

                # Obtém a correspondência mais próxima encontrada
                correspondencia = resultados[0].iloc[0]
                distancia = float(correspondencia["distance"])

                # Rejeita correspondências acima do limite definido
                if distancia > LIMITE_DISTANCIA:
                    atualizar_estado()
                    return {
                        "autenticado": False,
                        "mensagem": "Pessoa não identificada.",
                        "distancia": distancia
                    }

                # Recupera o ID a partir do caminho da imagem correspondente
                id_usuario = Path(
                    str(correspondencia["identity"])
                ).stem

                usuario = usuarios_por_id.get(id_usuario)

                if usuario is None:
                    atualizar_estado()
                    return {
                        "autenticado": False,
                        "mensagem": "Usuário correspondente não encontrado."
                    }

                id_usuario, cpf, nome, nivel = usuario

                # Registra o resultado para uso pelos outros módulos
                atualizar_estado(
                    autenticado=True,
                    id_usuario=id_usuario,
                    usuario=nome,
                    nivel_acesso=nivel,
                    distancia=distancia
                )

                return {
                    "autenticado": True,
                    "mensagem": "Usuário reconhecido.",
                    "id_usuario": id_usuario,
                    "cpf": cpf,
                    "usuario": nome,
                    "nivel_acesso": nivel,
                    "distancia": distancia
                }

        except Exception as erro:
            atualizar_estado()

            # Trata separadamente o caso em que nenhum rosto foi detectado
            if "Face could not be detected" in str(erro):
                return {
                    "autenticado": False,
                    "mensagem": "Nenhum rosto detectado na imagem."
                }

            logger.exception("Erro durante o reconhecimento facial.")
            raise
