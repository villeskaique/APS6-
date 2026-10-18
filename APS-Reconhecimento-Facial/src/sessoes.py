from secrets import token_urlsafe
from threading import Lock
from time import time

# Limites de duração das sessões
TEMPO_EXPIRACAO = 15 * 60
TEMPO_MAXIMO_SESSAO = 8 * 60 * 60

# Armazena as sessões ativas em memória
sessoes_ativas = {}
sessoes_lock = Lock()


def _expirada(sessao, agora):
    # Expira por inatividade ou pelo tempo total de duração
    inativa = agora - sessao["ultima_atividade"] > TEMPO_EXPIRACAO
    duracao_excedida = agora - sessao["criada_em"] > TEMPO_MAXIMO_SESSAO

    return inativa or duracao_excedida


def _remover_expiradas(agora):
    # Identifica e remove as sessões vencidas
    expiradas = [
        token
        for token, sessao in sessoes_ativas.items()
        if _expirada(sessao, agora)
    ]

    for token in expiradas:
        del sessoes_ativas[token]


def criar_sessao(id_usuario, usuario, nivel_acesso):
    # Gera um token difícil de adivinhar para identificar a sessão
    token = token_urlsafe(32)
    agora = time()

    with sessoes_lock:
        _remover_expiradas(agora)

        sessoes_ativas[token] = {
            "id_usuario": id_usuario,
            "usuario": usuario,
            "nivel_acesso": nivel_acesso,
            "criada_em": agora,
            "ultima_atividade": agora,
        }

    return token


def obter_sessao(token):
    agora = time()

    with sessoes_lock:
        sessao = sessoes_ativas.get(token)

        if sessao is None:
            return None

        if _expirada(sessao, agora):
            del sessoes_ativas[token]
            return None

        # Atualiza o horário para controlar a inatividade
        sessao["ultima_atividade"] = agora
        return sessao.copy()


def encerrar_sessao(token):
    # Remove a sessão e informa se ela existia
    with sessoes_lock:
        return sessoes_ativas.pop(token, None) is not None


def invalidar_sessoes():
    # Encerra todas as sessões ativas
    with sessoes_lock:
        sessoes_ativas.clear()
