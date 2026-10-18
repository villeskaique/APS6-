import os
from src.banco_dados import conectar


def cadastrar_usuario(cpf, nome, nivel_acesso, caminho_imagem, imagem=None):
    # Valida os dados antes de inserir o usuário
    if not cpf.isdigit() or len(cpf) != 11:
        raise ValueError("O CPF deve conter 11 dígitos.")

    if not 1 <= nivel_acesso <= 3:
        raise ValueError("O nível de acesso deve ser 1, 2 ou 3.")

    if imagem is not None and not isinstance(imagem, bytes):
        raise ValueError("A imagem deve ser fornecida em bytes.")

    # Insere o usuário e retorna o ID gerado pelo banco
    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO usuarios
                    (cpf, nome, nivel_acesso, caminho_imagem, imagem)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (cpf, nome, nivel_acesso, caminho_imagem, imagem)
            )

            return cursor.fetchone()[0]


def buscar_usuario_por_id(id_usuario):
    # Busca um usuário ativo pelo ID
    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cpf, nome, nivel_acesso, imagem
                FROM usuarios
                WHERE id = %s
                  AND ativo = TRUE
                """,
                (id_usuario,),
            )
            return cursor.fetchone()


def buscar_usuario_por_cpf(cpf):
    # Consulta os dados de um usuário pelo CPF
    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cpf, nome, nivel_acesso,
                       caminho_imagem, ativo
                FROM usuarios
                WHERE cpf = %s
                """,
                (cpf,)
            )

            return cursor.fetchone()


def buscar_usuario_por_nome(nome):
    # Compara nomes sem diferenciar letras maiúsculas de minúsculas
    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT cpf, nome, nivel_acesso
                FROM usuarios
                WHERE LOWER(nome) = LOWER(%s)
                  AND ativo = TRUE
                """,
                (nome.strip(),)
            )

            return cursor.fetchone()


def buscar_usuario_por_imagem(caminho_imagem):
    # Normaliza o caminho para facilitar a comparação entre arquivos
    caminho_procurado = os.path.realpath(caminho_imagem)

    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cpf, nome, nivel_acesso, caminho_imagem
                FROM usuarios
                WHERE ativo = TRUE
                """
            )
            usuarios = cursor.fetchall()

    # Procura o usuário cujo caminho corresponde à imagem informada
    for id_usuario, cpf, nome, nivel, imagem in usuarios:
        if os.path.normcase(os.path.realpath(imagem)).casefold() == \
                os.path.normcase(caminho_procurado).casefold():
            return id_usuario, cpf, nome, nivel


def listar_imagens_usuarios():
    # Retorna os usuários ativos que possuem imagem cadastrada
    with conectar() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cpf, nome, nivel_acesso, imagem
                FROM usuarios
                WHERE ativo = TRUE
                  AND imagem IS NOT NULL
                """
            )

            return cursor.fetchall()
