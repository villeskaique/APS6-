# Instalador do VerdeID

Executável que prepara todo o ambiente do projeto e sobe a aplicação.

**Nenhum arquivo original do projeto é modificado.** Tudo que o instalador cria
fica ou em `instalador/` ou em pastas novas já ignoradas pelo `.gitignore`
(`.venv/`, `.env`, `instalar.log`).

---

## Como usar

Dê dois cliques em:

```
instalador\InstaladorVerdeID.exe
```

Ou pelo PowerShell:

```powershell
cd instalador
.\InstaladorVerdeID.exe
```

Na primeira execução ele baixa as dependências (pode levar de 5 a 15 minutos).
Depois disso a inicialização leva poucos segundos.

Quando terminar, a API abre em <http://127.0.0.1:8000> no navegador.
Para encerrar a aplicação, pressione `Ctrl+C` na janela do instalador.

---

## Opções (linha de comando)

| Opção | O que faz |
|---|---|
| *(sem opção)* | Instala tudo e inicia a aplicação |
| `-SomenteInstalar` | Instala e configura, mas não sobe a aplicação |
| `-PularDependencias` | Pula o `pip install` (útil para reiniciar rápido) |
| `-PularBanco` | Não mexe no Docker/PostgreSQL (o app precisa de um banco já pronto) |
| `-RecriarBanco` | Apaga o volume do PostgreSQL e recria do zero |
| `-LiberarPortaPostgres` | Para o serviço do Windows que ocupa a porta 5432, sem perguntar |
| `-ExecutarTestes` | Roda a suíte `tests/` depois de preparar o ambiente |
| `-NaoAbrirNavegador` | Não abre o navegador ao iniciar |
| `-ManterJanela` | Mantém a janela do console aberta ao final |

Exemplo:

```powershell
.\InstaladorVerdeID.exe -PularDependencias -ExecutarTestes
```

O mesmo pode ser feito direto pelo script, sem o `.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar.ps1 -SomenteInstalar
```

---

## O que ele faz, etapa a etapa

| # | Etapa | Detalhe |
|---|---|---|
| 1 | Python + `.venv` | Procura Python 3.10+ (PATH, `py -3`, instaladores padrão) e cria o ambiente virtual `.venv` na raiz |
| 2 | Dependências | `pip install -r requirements.txt` + `instalador/dependencias-extras.txt`; ao final faz o smoke test `import api` |
| 3 | `.env` | Cria `.env` com uma `POSTGRES_PASSWORD` aleatória (se já existir, mantém como está) |
| 4 | Docker | Sobe o Docker Desktop se estiver parado, roda `docker compose up -d` e espera o healthcheck |
| 5 | Banco | Aplica `inicializacao.sql` + `instalador/sql/03_coluna_imagem.sql` via `docker cp`/`psql` e valida o schema |
| 6 | Testes | Opcional (`-ExecutarTestes`) |
| 7 | Aplicação | `python -m src.main` com `PYTHONPATH=.;src` e abre o navegador |

O log completo fica em `instalador/instalar.log`.

---

## Problemas encontrados na análise do projeto

Estes pontos quebram a execução em uma instalação limpa. Como os arquivos
originais não podem ser alterados, o instalador resolve cada um em tempo de
execução:

1. **`python-multipart` ausente** — `src/api.py` usa `Form` e `UploadFile`, e o
   FastAPI levanta `RuntimeError` na importação do módulo. Sem isso a aplicação
   nem sobe. Instalado via `instalador/dependencias-extras.txt`.

2. **`python-dotenv` ausente no `requirements.txt`** — usado por
   `src/banco_dados.py` para ler o `.env`. Adicionado no mesmo arquivo de extras.

3. **Coluna `usuarios.imagem` não existe** — `inicializacao.sql` cria a tabela
   `usuarios` sem a coluna `imagem BYTEA`, mas `src/usuarios.py` faz `INSERT` e
   `SELECT` nessa coluna (`cadastrar_usuario`, `listar_imagens_usuarios`).
   O instalador aplica `instalador/sql/03_coluna_imagem.sql`, que cria a coluna
   de forma idempotente (`ADD COLUMN IF NOT EXISTS`), sem tocar no SQL do projeto.

4. **`.env` inexistente** — `compose.yaml` usa `env_file: .env` e
   `src/banco_dados.py` lê `os.environ["POSTGRES_PASSWORD"]`. Sem o arquivo, o
   banco nem sobe. O instalador cria um com senha aleatória.

Observações que não bloqueiam a instalação:

- `requirements.txt` traz `httpx2`, que é um pacote real do PyPI (não é typo de
  `httpx`) e está instalado normalmente.
- O DeepFace roda com backend ONNX (`onnnxruntime` vem como dependência dele),
  então **TensorFlow não é necessário** — instalação bem mais leve.
- `src/main.py` importa os módulos de duas formas (`from src.usuarios` e
  `from usuarios`). Por isso o `PYTHONPATH` precisa conter `.` e `src`, como o
  instalador configura.

---

## Pré-requisitos

- **Python 3.10+** — o instalador procura sozinho; se não achar, orienta o
  download em python.org (marque *"Add Python to PATH"*).
- **Docker Desktop** — instalado, mas precisa conseguir subir. O instalador
  localiza o `Docker Desktop.exe` pelo registro e o inicia sozinho, depois
  aguarda até 10 minutos.
- **Windows** — o `.exe` é compilado com o `csc.exe` do .NET Framework nativo.

---

## Recriando o executável

Depois de editar `instalar.ps1` ou `InstaladorVerdeID.cs`:

```powershell
cd instalador
powershell -ExecutionPolicy Bypass -File .\compilar.ps1
```

O `compilar.ps1` embute o `instalar.ps1` dentro do `.exe` como recurso
embutido, então o executável funciona sozinho, sem depender do script ao lado.