-- Tabela de usuários cadastrados para reconhecimento facial
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER GENERATED ALWAYS AS IDENTITY UNIQUE NOT NULL,
    cpf CHAR(11) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    nivel_acesso SMALLINT NOT NULL
        CHECK (nivel_acesso BETWEEN 1 AND 3),
    caminho_imagem VARCHAR(255) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de informações ambientais protegidas por nível de acesso
CREATE TABLE IF NOT EXISTS dados_ambientais (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    descricao TEXT NOT NULL,
    nivel_acesso SMALLINT NOT NULL
        CHECK (nivel_acesso BETWEEN 1 AND 3)
);

-- Dados iniciais de exemplo para testar os níveis de acesso
INSERT INTO dados_ambientais (descricao, nivel_acesso)
SELECT dados.descricao, dados.nivel_acesso
FROM (
    VALUES
        ('Informações públicas sobre fiscalização ambiental', 1),
        ('Orientações gerais sobre uso de agrotóxicos', 1),
        ('Relatórios internos de fiscalização', 2),
        ('Dados de propriedades rurais em investigação', 2),
        ('Relatório estratégico nacional', 3),
        ('Informações restritas para decisão ministerial', 3)
) AS dados(descricao, nivel_acesso)
WHERE NOT EXISTS (
    SELECT 1
    FROM dados_ambientais AS existente
    WHERE existente.descricao = dados.descricao
      AND existente.nivel_acesso = dados.nivel_acesso
);