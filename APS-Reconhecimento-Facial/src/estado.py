from threading import Lock
from time import time

estado_lock = Lock()

# Guarda o resultado mais recente do reconhecimento facial
estado_reconhecimento = {
    "autenticado": False,
    "id_usuario": None,
    "usuario": None,
    "nivel_acesso": 0,
    "distancia": None,
    "atualizado_em": 0,
}


def atualizar_estado(
    autenticado=False,
    id_usuario=None,
    usuario=None,
    nivel_acesso=0,
    distancia=None,
):
    # Atualiza o estado compartilhado de forma segura
    with estado_lock:
        estado_reconhecimento.update({
            "autenticado": autenticado,
            "id_usuario": id_usuario if autenticado else None,
            "usuario": usuario if autenticado else None,
            "nivel_acesso": nivel_acesso if autenticado else 0,
            "distancia": distancia if autenticado else None,
            "atualizado_em": time(),
        })


def obter_estado():
    with estado_lock:
        estado = estado_reconhecimento.copy()

    # Considera a autenticação válida por até 3 segundos
    if time() - estado["atualizado_em"] > 3:
        estado.update({
            "autenticado": False,
            "id_usuario": None,
            "usuario": None,
            "nivel_acesso": 0,
            "distancia": None,
        })

    # Remove o horário interno antes de retornar os dados
    estado.pop("atualizado_em", None)
    return estado
