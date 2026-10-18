-- Correcao idempotente aplicada pelo instalador.
--
-- O codigo da aplicacao (src/usuarios.py) grava e le a coluna "imagem" (BYTEA),
-- mas o inicializacao.sql do projeto cria a tabela "usuarios" sem essa coluna.
-- Sem ela o cadastro de usuarios e o reconhecimento facial falham com
-- "column imagem does not exist".
--
-- O comando e idempotente: pode ser executado quantas vezes for necessario.

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS imagem BYTEA;

-- Garante que a tabela exista antes do ALTER (caso o inicializacao.sql nao tenha rodado).
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER GENERATED ALWAYS AS IDENTITY UNIQUE NOT NULL,
    cpf CHAR(11) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    nivel_acesso SMALLINT NOT NULL
        CHECK (nivel_acesso BETWEEN 1 AND 3),
    caminho_imagem VARCHAR(255) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imagem BYTEA
);