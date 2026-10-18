import logging
import psycopg

from banco_dados import conectar

logger = logging.getLogger(__name__)


def pode_acessar(nivel_usuario, nivel_recurso):
    # Usuários com nível igual ou superior podem acessar o recurso
    return nivel_usuario >= nivel_recurso


def consultar_dados(nome, nivel_usuario, nivel_recurso):
    # Aceita somente os níveis de recurso definidos pelo sistema
    if nivel_recurso not in (1, 2, 3):
        return {
            "sucesso": False,
            "mensagem": "Nível de recurso inválido.",
            "dados": []
        }

    if not pode_acessar(nivel_usuario, nivel_recurso):
        return {
            "sucesso": False,
            "mensagem": "Acesso negado.",
            "dados": []
        }

    try:
        # Busca no banco os dados correspondentes ao nível solicitado
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute("""
                    SELECT descricao
                    FROM dados_ambientais
                    WHERE nivel_acesso = %s
                    ORDER BY id
                """, (nivel_recurso,))

                dados = [linha[0] for linha in cursor.fetchall()]

    except psycopg.Error:
        # Registra os detalhes do erro sem expô-los ao cliente
        logger.exception(
            "Falha ao consultar dados ambientais no PostgreSQL."
        )

        return {
            "sucesso": False,
            "mensagem": "Não foi possível consultar os dados no momento.",
            "dados": []
        }

    return {
        "sucesso": True,
        "mensagem": "Acesso autorizado.",
        "usuario": nome,
        "nivel_acesso": nivel_usuario,
        "nivel_recurso": nivel_recurso,
        "dados": dados
    }
