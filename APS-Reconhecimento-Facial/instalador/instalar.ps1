#Requires -Version 5.1

<#
    Instalador do VerdeID (APS - Reconhecimento Facial)

    Prepara todo o ambiente do zero e sobe a aplicacao:
      1. Localiza/valida o Python e cria o ambiente virtual .venv
      2. Instala as dependencias do requirements.txt + extras
      3. Cria o arquivo .env com a senha do PostgreSQL
      4. Sobe o PostgreSQL 17 via Docker Compose
      5. Aplica o inicializacao.sql do projeto + correcoes idempotentes
      6. (opcional) roda a suite de testes
      7. Inicia a API em http://127.0.0.1:8000 e abre o navegador

    Este script NAO modifica nenhum arquivo original do projeto.
#>

[CmdletBinding()]
param(
    [string] $Raiz,
    [switch] $SomenteInstalar,
    [switch] $PularBanco,
    [switch] $RecriarBanco,
    [switch] $PularDependencias,
    [switch] $ExecutarTestes,
    [switch] $NaoAbrirNavegador,
    [switch] $LiberarPortaPostgres,
    [switch] $ManterJanela
)

# Erros de comandos nativos (uvicorn escreve log em stderr) nao devem abortar o script.
$ErrorActionPreference = 'Continue'

# --------------------------------------------------------------------------
# Configuracao
# --------------------------------------------------------------------------

$script:BaseDir   = $PSScriptRoot

$NomeContainer  = 'aps-postgres'
$UsuarioBanco   = 'aps_user'
$NomeBanco      = 'aps_reconhecimento_facial'
$PortaApp       = 8000
$UrlApp         = 'http://127.0.0.1:8000'

$NomePythonMinimo = [version]'3.10.0'

if ([string]::IsNullOrWhiteSpace($Raiz)) {
    $Raiz = Split-Path -Parent $script:BaseDir
}

if (-not (Test-Path -LiteralPath $Raiz)) {
    Write-Host "ERRO: raiz do projeto nao encontrada: $Raiz" -ForegroundColor Red
    exit 1
}

$script:Raiz   = (Resolve-Path -LiteralPath $Raiz).Path
$script:Venv   = Join-Path $script:Raiz '.venv'
$script:VenvPy = Join-Path $script:Venv 'Scripts\python.exe'
$script:EnvArq = Join-Path $script:Raiz '.env'

# O log fica sempre na pasta "instalador" do projeto. Quando o script vem
# embutido no .exe ele e extraido para o %TEMP%, e o log deve ir para o projeto.
$pastaInstalador = Join-Path $script:Raiz 'instalador'

if (Test-Path -LiteralPath $pastaInstalador) {
    $script:LogPath = Join-Path $pastaInstalador 'instalar.log'
}
else {
    $script:LogPath = Join-Path $script:BaseDir 'instalar.log'
}

$script:LockPath = Join-Path (Split-Path -Parent $script:LogPath) 'instalar.lock'

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

$nivelCor = @{
    'INFO'   = 'Cyan'
    'OK'     = 'Green'
    'AVISO'  = 'Yellow'
    'ERRO'   = 'Red'
    'SAIDA'  = 'DarkGray'
    'PASSO'  = 'White'
}

function Escrever-Log {
    param(
        [string] $Nivel = 'INFO',
        [string] $Mensagem
    )

    $carimbo = (Get-Date).ToString('HH:mm:ss')
    $cor    = $nivelCor[$Nivel]
    $texto  = "[$carimbo] $Mensagem"

    Write-Host $texto -ForegroundColor $cor

    try {
        Add-Content -LiteralPath $script:LogPath -Value "$carimbo [$Nivel] $Mensagem" -Encoding UTF8
    } catch {
        # Falha ao gravar log nunca deve interromper a instalacao.
    }
}

function Escrever-Titulo {
    param([string] $Texto)

    Write-Host ''
    Write-Host ("=" * 74) -ForegroundColor DarkCyan
    Write-Host "  $Texto" -ForegroundColor Cyan
    Write-Host ("=" * 74) -ForegroundColor DarkCyan
}

function Escrever-Passo {
    param([string] $Texto)

    Write-Host ''
    Write-Host ">> $Texto" -ForegroundColor White
}

# --------------------------------------------------------------------------
# Processos
# --------------------------------------------------------------------------

# Executa um processo externo exibindo e salvando a saida em tempo real.
function Invoke-Processo {
    param(
        [Parameter(Mandatory = $true)][string] $Arquivo,
        [string[]] $Argumentos = @(),
        [string] $Descricao = '',
        [int[]]   $CodigosAceitos = @(0),
        [string] $Pasta = $null,
        [switch] $Silencioso
    )

    $rotulo = if ($Descricao) { $Descricao } else { $Arquivo }
    Escrever-Log -Nivel 'INFO' -Mensagem ("$rotulo  ->  $Argumentos")

    if ($Pasta) { Push-Location -LiteralPath $Pasta }

    try {
        & $Arquivo @Argumentos 2>&1 | ForEach-Object {
            $linha = [string]$_

            if (-not [string]::IsNullOrWhiteSpace($linha)) {
                if ($Silencioso) {
                    Escrever-Log -Nivel 'SAIDA' -Mensagem "    $linha"
                } else {
                    Write-Host "    $linha" -ForegroundColor DarkGray
                    Add-Content -LiteralPath $script:LogPath -Value "    $linha" -Encoding UTF8 -ErrorAction SilentlyContinue
                }
            }
        }

        $codigo = $LASTEXITCODE

        if ($CodigosAceitos -notcontains $codigo) {
            Escrever-Log -Nivel 'ERRO' -Mensagem "$rotulo falhou com codigo $codigo."
            throw "$rotulo falhou com codigo de saida $codigo."
        }

        return $codigo
    }
    finally {
        if ($Pasta) { Pop-Location }
    }
}

# Executa um processo curto e devolve a saida como texto.
function Invoke-Capturar {
    param(
        [Parameter(Mandatory = $true)][string] $Arquivo,
        [string[]] $Argumentos = @()
    )

    $saida = & $Arquivo @Argumentos 2>&1
    return ($saida | Out-String).Trim()
}

function Testar-Comando {
    param([string] $Nome)
    return [bool] (Get-Command $Nome -ErrorAction SilentlyContinue)
}

function Resolver-Recurso {
    param([string] $Relativo)

    $candidatos = @(
        (Join-Path $script:Raiz (Join-Path 'instalador' $Relativo)),
        (Join-Path $script:BaseDir $Relativo)
    )

    foreach ($candidato in $candidatos) {
        if ($candidato -and (Test-Path -LiteralPath $candidato)) {
            return (Resolve-Path -LiteralPath $candidato).Path
        }
    }

    return $null
}

function Aguardar {
    param([int] $Segundos, [string] $Mensagem)

    for ($i = 0; $i -lt $Segundos; $i++) {
        Start-Sleep -Seconds 1

        if ($i % 10 -eq 9) {
            Escrever-Log -Nivel 'INFO' -Mensagem "$Mensagem ($($i + 1)s/$Segundos)s"
        }
    }
}

# --------------------------------------------------------------------------
# Trava contra execucoes duplicadas
# --------------------------------------------------------------------------

# Sem isso, dois cliques no .exe rodariam dois instaladores ao mesmo tempo,
# disputando o .venv, o Docker e o mesmo arquivo de log.
function Bloquear-Execucao {
    if (Test-Path -LiteralPath $script:LockPath) {
        $conteudo = Get-Content -LiteralPath $script:LockPath -Raw -ErrorAction SilentlyContinue
        $pidAnterior = 0

        if ($conteudo -match 'pid=(\d+)') {
            $pidAnterior = [int]$Matches[1]
        }

        $processoVivo = $null

        if ($pidAnterior -gt 0 -and $pidAnterior -ne $PID) {
            $processoVivo = Get-Process -Id $pidAnterior -ErrorAction SilentlyContinue
        }

        if ($processoVivo) {
            throw "Ja existe uma instalacao em andamento (processo $pidAnterior). Aguarde ela terminar ou feche a outra janela antes de rodar de novo."
        }
    }

    Set-Content -LiteralPath $script:LockPath `
                -Value "pid=$PID`ninicio=$((Get-Date).ToString('s'))" `
                -Encoding ASCII
}

function Liberar-Execucao {
    Remove-Item -LiteralPath $script:LockPath -Force -ErrorAction SilentlyContinue
}

# Filtra a saida de comandos docker, mantendo apenas IDs de container.
function Obter-Ids {
    param([string[]] $Argumentos)

    $saida = Invoke-Capturar -Arquivo 'docker' -Argumentos $Argumentos

    return @($saida -split '\s+' | Where-Object { $_ -match '^[0-9a-f]{12,64}$' })
}

# Procura pelo nome exato. O filtro "name=" do Docker casa por substring e
# ignora ancoras, entao a conferencia final e feita pelo nome devolvido.
function Obter-IdPorNome {
    param([string] $Nome)

    $linhas = Invoke-Capturar -Arquivo 'docker' -Argumentos @('ps', '-a', '--format', '{{.ID}}|{{.Names}}')

    foreach ($linha in ($linhas -split "`r?`n")) {
        if ($linha -match '^([0-9a-f]{12,64})\|\s*(.+?)\s*$' -and $Matches[2] -eq $Nome) {
            return $Matches[1]
        }
    }

    return $null
}

# Estado do container, sem o barulho do erro do Docker quando ele ainda nao existe.
function Obter-EstadoContainer {
    param([string] $Nome)

    $modelo = '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'

    $saida = & 'docker' inspect --format $modelo $Nome 2>$null

    if ($LASTEXITCODE -ne 0 -or -not $saida) {
        return 'inexistente'
    }

    return ($saida | Out-String).Trim()
}

# --------------------------------------------------------------------------
# Etapa 1 - Python e ambiente virtual
# --------------------------------------------------------------------------

function Obter-VersaoPython {
    param([string] $Executavel, [string[]] $Prefixo = @())

    # Usa a flag -V em vez de "-c": uma linha de codigo com aspas internas
    # chega embaralhada ao executavel quando passada pelo PowerShell 5.1.
    $saida = Invoke-Capturar -Arquivo $Executavel -Argumentos ($Prefixo + @('-V'))

    if ($saida -match '(\d+)\.(\d+)\.(\d+)') {
        return [version] "$($Matches[1]).$($Matches[2]).$($Matches[3])"
    }

    return $null
}

function Encontrar-PythonSistema {
    $candidatos = New-Object System.Collections.Generic.List[object]

    if (Testar-Comando 'py') {
        $candidatos.Add(@{ Arquivo = 'py'; Argumentos = @('-3') })
    }

    if (Testar-Comando 'python') {
        $candidatos.Add(@{ Arquivo = 'python'; Argumentos = @() })
    }

    if (Testar-Comando 'python3') {
        $candidatos.Add(@{ Arquivo = 'python3'; Argumentos = @() })
    }

    # Instalacoes padrao do Python no Windows.
    $padroes = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe')
    )

    if ($env:ProgramFiles) {
        $padroes += (Join-Path $env:ProgramFiles 'Python*\python.exe')
    }

    foreach ($padrao in $padroes) {
        foreach ($achado in (Get-ChildItem -Path $padrao -ErrorAction SilentlyContinue)) {
            $candidatos.Add(@{ Arquivo = $achado.FullName; Argumentos = @() })
        }
    }

    foreach ($candidato in $candidatos) {
        Escrever-Log -Nivel 'INFO' -Mensagem "Verificando $($candidato.Arquivo) $($candidato.Argumentos -join ' ')..."
        $versao = Obter-VersaoPython -Executavel $candidato.Arquivo -Prefixo $candidato.Argumentos

        if ($versao -and $versao -ge $NomePythonMinimo) {
            return [pscustomobject]@{
                Executavel = (Get-Command $candidato.Arquivo -ErrorAction SilentlyContinue).Source
                Versao     = $versao
            }
        }
    }

    return $null
}

function Preparar-AmbienteVirtual {
    Escrever-Passo '1/7  Preparando o ambiente Python'

    if (Test-Path -LiteralPath $script:VenvPy) {
        $versaoVenv = Obter-VersaoPython -Executavel $script:VenvPy

        if ($versaoVenv) {
            Escrever-Log -Nivel 'OK' -Mensagem "Ambiente virtual ja existe: .venv (Python $versaoVenv)"
            return $script:VenvPy
        }

        Escrever-Log -Nivel 'AVISO' -Mensagem '.venv encontrado porem invalido. sera recriado.'
        Remove-Item -LiteralPath $script:Venv -Recurse -Force -ErrorAction SilentlyContinue
    }

    $pythonSistema = Encontrar-PythonSistema

    if (-not $pythonSistema) {
        throw "Python $($NomePythonMinimo) ou superior nao encontrado. Instale em https://www.python.org/downloads/ marcando 'Add Python to PATH'."
    }

    Escrever-Log -Nivel 'OK' -Mensagem "Python detectado: $($pythonSistema.Executavel) ($($pythonSistema.Versao))"

    Escrever-Log -Nivel 'INFO' -Mensagem "Criando o ambiente virtual em $script:Venv ..."
    Invoke-Processo -Arquivo $pythonSistema.Executavel `
                   -Argumentos @('-m', 'venv', $script:Venv) `
                   -Descricao 'python -m venv' | Out-Null

    if (-not (Test-Path -LiteralPath $script:VenvPy)) {
        throw "Falha ao criar o ambiente virtual em $script:Venv."
    }

    $versaoVenv = Obter-VersaoPython -Executavel $script:VenvPy
    Escrever-Log -Nivel 'OK' -Mensagem "Ambiente virtual criado com Python $versaoVenv"
    return $script:VenvPy
}

# --------------------------------------------------------------------------
# Etapa 2 - Dependencias Python
# --------------------------------------------------------------------------

function Instalar-Dependencias {
    param([string] $Python)

    Escrever-Passo '2/7  Instalando as dependencias Python'

    Escrever-Log -Nivel 'INFO' -Mensagem 'Atualizando pip, setuptools e wheel...'
    Invoke-Processo -Arquivo $Python `
                   -Argumentos @('-m', 'pip', 'install', '--upgrade', '--disable-pip-version-check', 'pip', 'setuptools', 'wheel') `
                   -Descricao 'pip upgrade' -Silencioso | Out-Null

    $requirements = Join-Path $script:Raiz 'requirements.txt'

    if (-not (Test-Path -LiteralPath $requirements)) {
        throw "requirements.txt nao encontrado em $script:Raiz."
    }

    $extras = Resolver-Recurso 'dependencias-extras.txt'
    $argumentos = @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', $requirements)

    if ($extras) {
        Escrever-Log -Nivel 'INFO' -Mensagem "Dependencias extras: $extras"
        $argumentos += @('-r', $extras)
    }

    Escrever-Log -Nivel 'AVISO' -Mensagem 'A primeira instalacao pode levar alguns minutos (DeepFace, OpenCV, onnxruntime).'

    # Em pastas sincronizadas pelo OneDrive o pip costuma falhar com
    # "WinError 32: o arquivo ja esta sendo usado por outro processo".
    # Nesses casos basta repetir: o cache local do pip evita baixar tudo de novo.
    $tentativas = 3

    for ($tentativa = 1; $tentativa -le $tentativas; $tentativa++) {
        try {
            Invoke-Processo -Arquivo $Python -Argumentos $argumentos -Descricao 'pip install -r requirements.txt' -Silencioso | Out-Null
            break
        }
        catch {
            if ($tentativa -eq $tentativas) {
                throw
            }

            Escrever-Log -Nivel 'AVISO' -Mensagem "Falha ao instalar as dependencias (tentativa $tentativa de $tentativas)."
            Escrever-Log -Nivel 'AVISO' -Mensagem 'Se o erro for "arquivo ja esta sendo usado", o OneDrive esta bloqueando o .venv. Isso se resolve tentando de novo.'
            Start-Sleep -Seconds 10
        }
    }

    Escrever-Log -Nivel 'OK' -Mensagem 'Dependencias instaladas.'

    # Falha mais comum ao rodar sem a dependencia certa: validar o import da API.
    # Precisa da raiz do projeto no PYTHONPATH e no diretorio de trabalho,
    # porque os modulos são importados como "src.x" e como "x".
    $env:PYTHONPATH = "$script:Raiz;$($script:Raiz)\src"
    $env:PYTHONUTF8 = '1'

    Invoke-Processo -Arquivo $Python `
                   -Argumentos @('-c', 'import api') `
                   -Descricao 'Validacao: import api' `
                   -Pasta $script:Raiz | Out-Null

    Escrever-Log -Nivel 'OK' -Mensagem "Validacao de importacao: OK (modulo 'api' carregou)."
}

# --------------------------------------------------------------------------
# Etapa 3 - Arquivo .env
# --------------------------------------------------------------------------

function Preparar-Env {
    Escrever-Passo '3/7  Configurando o arquivo .env'

    if (-not (Test-Path -LiteralPath $script:EnvArq)) {
        $bytes = New-Object byte[] 24
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $senha = ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()

        $conteudo = @(
            '# Criado automaticamente pelo instalador do VerdeID.'
            "# Gerado em $((Get-Date).ToString('dd/MM/yyyy HH:mm:ss'))"
            '# POSTGRES_USER e POSTGRES_DB vem do compose.yaml do projeto.'
            "POSTGRES_PASSWORD=$senha"
            ''
        )

        Set-Content -LiteralPath $script:EnvArq -Value $conteudo -Encoding UTF8
        Escrever-Log -Nivel 'OK' -Mensagem "Arquivo .env criado em $script:EnvArq"
        return
    }

    Escrever-Log -Nivel 'OK' -Mensagem "Arquivo .env ja existe (mantido como esta): $script:EnvArq"

    $senhaAtual = $null

    foreach ($linha in (Get-Content -LiteralPath $script:EnvArq)) {
        if ($linha -match '^\s*POSTGRES_PASSWORD\s*=\s*(.+?)\s*$') {
            $senhaAtual = $Matches[1]
        }
    }

    if (-not $senhaAtual) {
        Escrever-Log -Nivel 'AVISO' -Mensagem 'POSTGRES_PASSWORD nao encontrada no .env. O PostgreSQL nao podera iniciar.'
        throw 'Defina POSTGRES_PASSWORD no arquivo .env e rode o instalador novamente.'
    }
}

# --------------------------------------------------------------------------
# Etapa 4 e 5 - Docker + banco de dados
# --------------------------------------------------------------------------

function Testar-DockerAtivo {
    Invoke-Capturar -Arquivo 'docker' -Argumentos @('info', '--format', '{{.ServerVersion}}') | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Encontrar-DockerDesktop {
    $caminhos = New-Object System.Collections.Generic.List[string]
    $chaves = @(
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )

    foreach ($chave in $chaves) {
        Get-ItemProperty $chave -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like 'Docker Desktop*' -and $_.InstallLocation } |
            ForEach-Object { $caminhos.Add((Join-Path $_.InstallLocation 'Docker Desktop.exe')) }
    }

    if ($env:LOCALAPPDATA) {
        $caminhos.Add((Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'))
    }

    if ($env:ProgramFiles) {
        $caminhos.Add((Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'))
    }

    if (${env:ProgramFiles(x86)}) {
        $caminhos.Add((Join-Path ${env:ProgramFiles(x86)} 'Docker\Docker\Docker Desktop.exe'))
    }

    foreach ($caminho in $caminhos) {
        if ($caminho -and (Test-Path -LiteralPath $caminho)) {
            return $caminho
        }
    }

    return $null
}

function Iniciar-Docker {
    Escrever-Passo '4/7  Subindo o PostgreSQL com Docker'

    if (-not (Testar-Comando 'docker')) {
        throw 'Docker nao encontrado. Instale o Docker Desktop em https://www.docker.com/products/docker-desktop/'
    }

    if (Testar-DockerAtivo) {
        Escrever-Log -Nivel 'OK' -Mensagem 'Docker ja esta em execucao.'
        return
    }

    $dockerDesktop = Encontrar-DockerDesktop

    if (-not $dockerDesktop) {
        throw 'O Docker esta instalado mas o servico nao responde e o Docker Desktop.exe nao foi encontrado. Abra o Docker Desktop manualmente e rode o instalador de novo.'
    }

    Escrever-Log -Nivel 'INFO' -Mensagem "Iniciando o Docker Desktop: $dockerDesktop"
    Start-Process -FilePath $dockerDesktop | Out-Null
    Escrever-Log -Nivel 'AVISO' -Mensagem 'Aguardando o Docker Desktop subir (pode levar 1-2 minutos)...'

    $iniciou = $false

    for ($i = 0; $i -lt 300; $i++) {
        Start-Sleep -Seconds 2

        if (Testar-DockerAtivo) {
            $iniciou = $true
            break
        }

        if ($i % 10 -eq 9) {
            Escrever-Log -Nivel 'INFO' -Mensagem "Aguardando Docker ($([math]::Round(($i + 1) * 2))s)..."
        }
    }

    if (-not $iniciou) {
        throw 'O Docker nao respondeu em 10 minutos. Verifique se o Docker Desktop iniciou corretamente.'
    }

    Escrever-Log -Nivel 'OK' -Mensagem 'Docker pronto.'
}

function Testar-Administrador {
    try {
        $identidade = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identidade)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        return $false
    }
}

# Para o servico do Windows. Sem privilegio de administrador, cria um script
# temporario e o executa como administrador (o usuario ve o prompt do UAC).
function Parar-ServicoPostgres {
    param([string] $NomeServico)

    if (Testar-Administrador) {
        Stop-Service -Name $NomeServico -Force -ErrorAction Stop
        return $true
    }

    $scriptAuxiliar = Join-Path $env:TEMP "verdeid-parar-servico.ps1"

    Set-Content -LiteralPath $scriptAuxiliar `
                -Value "Stop-Service -Name '$NomeServico' -Force -ErrorAction Stop" `
                -Encoding UTF8

    try {
        Escrever-Log -Nivel 'AVISO' -Mensagem 'Solicitando permissao de administrador (confirme no UAC)...'

        Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') `
                      -Verb RunAs `
                      -Wait `
                      -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$scriptAuxiliar`"") | Out-Null
    }
    finally {
        Remove-Item -LiteralPath $scriptAuxiliar -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 3

    $servico = Get-Service -Name $NomeServico -ErrorAction SilentlyContinue

    if ($servico -and $servico.Status -eq 'Running') {
        return $false
    }

    return $true
}

# Descobre qual servico do Windows dona da porta. O processo que escuta
# normalmente e um filho do processo do servico (no PostgreSQL, os backends
# sao filhos do postmaster), entao a arvore de processos precisa ser percorrida.
function Obter-ServicoDaPorta {
    param([int] $ProcessoId)

    $atual = $ProcessoId

    for ($nivel = 0; $nivel -lt 6; $nivel++) {
        if (-not $atual -or $atual -le 0) { break }

        $servico = Get-CimInstance Win32_Service -Filter "ProcessId = $atual" -ErrorAction SilentlyContinue |
            Select-Object -First 1

        if ($servico) {
            return $servico
        }

        $processo = Get-CimInstance Win32_Process -Filter "ProcessId = $atual" -ErrorAction SilentlyContinue

        if (-not $processo) { break }

        $atual = $processo.ParentProcessId
    }

    return $null
}

# O compose.yaml publica a porta 5432 no host. Se ela ja estiver ocupada por
# outro servico (por exemplo um PostgreSQL instalado nativamente no Windows),
# o Docker falha com um erro de socket confuso. Melhor detectar antes.
function Verificar-PortaPostgres {
    $conexoes = @()

    try {
        $conexoes = @(Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue)
    }
    catch {
        return
    }

    if ($conexoes.Count -eq 0) { return }

    $processos = @()

    foreach ($conexao in $conexoes) {
        $processo = Get-Process -Id $conexao.OwningProcess -ErrorAction SilentlyContinue

        if ($processo) {
            $processos += $processo
        }
    }

    $nomes = @($processos | Select-Object -ExpandProperty ProcessName -Unique)
    $lista = $nomes -join ', '

    # Se quem escuta e o proprio Docker, e o container de outro servico do projeto.
    if ($nomes -contains 'docker' -or $nomes -contains 'com.docker.backend') {
        return
    }

    $servico = Obter-ServicoDaPorta -ProcessoId $conexoes[0].OwningProcess

    # Reserva: se a arvore nao puder ser lida, casa pelo nome do processo.
    if (-not $servico -and $nomes.Count -gt 0) {
        $nomeProcesso = $nomes[0]

        $servico = Get-Service -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Status -eq 'Running' -and
                ($_.Name -like "$nomeProcesso*" -or $_.DisplayName -like "*$nomeProcesso*")
            } |
            Select-Object -First 1
    }

    if (-not $servico) {
        Escrever-Log -Nivel 'ERRO' -Mensagem "A porta 5432 ja esta em uso por: $lista."
        Escrever-Log -Nivel 'ERRO' -Mensagem 'Encerre esse processo (ou o servico correspondente) e rode o instalador novamente.'
        throw 'Porta 5432 ocupada.'
    }

    $nomeServico = $servico.Name
    $rotuloServico = $servico.DisplayName

    Escrever-Log -Nivel 'AVISO' -Mensagem "A porta 5432 esta em uso pelo servico do Windows '$nomeServico' ($rotuloServico)."

    $parar = $LiberarPortaPostgres
    $interativo = $true

    try { $interativo = -not [Console]::IsInputRedirected } catch { }

    if (-not $parar -and $interativo) {
        Write-Host ''
        Write-Host "  Este servico e um PostgreSQL instalado fora do Docker." -ForegroundColor Yellow
        Write-Host "  O projeto precisa da porta 5432 para subir o banco em Docker." -ForegroundColor Yellow
        Write-Host "  Voce pode iniciar o servico de novo depois com:" -ForegroundColor Yellow
        Write-Host "      Start-Service $nomeServico" -ForegroundColor DarkGray
        Write-Host ''

        $resposta = Read-Host '  Parar o servico agora? [S/N]'

        $parar = ($resposta -match '^[SsYy]')
    }

    if ($parar) {
        Escrever-Log -Nivel 'INFO' -Mensagem "Parando o servico $nomeServico..."

        if (-not (Parar-ServicoPostgres -NomeServico $nomeServico)) {
            throw "Nao foi possivel parar o servico $nomeServico. Tente manualmente em um PowerShell como Administrador."
        }

        Escrever-Log -Nivel 'OK' -Mensagem "Servico $nomeServico parado. Porta 5432 liberada."
        return
    }

    Escrever-Log -Nivel 'ERRO' -Mensagem "Libere a porta 5432 e rode o instalador novamente (ou use -LiberarPortaPostgres)."
    throw 'Porta 5432 ocupada.'
}

function Garantir-ContainerLivre {
    $compose = Join-Path $script:Raiz 'compose.yaml'

    # Containers que este compose.yaml gerencia.
    $gerenciados = Obter-Ids @('compose', '-f', $compose, 'ps', '-a', '-q')

    # Containers com o nome fixo declarado em container_name no compose.yaml.
    # Se vierem de outra instalacao do Compose, o "up" falha com
    # "the container name is already in use".
    $idNomeFixo = Obter-IdPorNome -Nome $NomeContainer

    if ($idNomeFixo -and $gerenciados -notcontains $idNomeFixo) {
        Escrever-Log -Nivel 'AVISO' -Mensagem "Removendo o container '$NomeContainer' ($idNomeFixo) deixado por outra instalacao do Docker Compose."
        Escrever-Log -Nivel 'AVISO' -Mensagem 'Os volumes com os dados do banco sao preservados.'
        Invoke-Processo -Arquivo 'docker' -Argumentos @('rm', '-f', $idNomeFixo) -Descricao "docker rm -f $idNomeFixo" | Out-Null
    }

    # Containers parados deste projeto travam a recriacao do servico.
    if ($gerenciados.Count -gt 0) {
        $rodando = Obter-Ids @('ps', '-q')
        $parados = @($gerenciados | Where-Object { $rodando -notcontains $_ })

        if ($parados.Count -gt 0) {
            Escrever-Log -Nivel 'INFO' -Mensagem 'Recriando containers parados deste projeto...'
            Invoke-Processo -Arquivo 'docker' `
                           -Argumentos @('compose', '-f', $compose, 'down', '--remove-orphans', '--timeout', '10') `
                           -Descricao 'docker compose down --remove-orphans' | Out-Null
        }
    }
}

function Subir-Container {
    $compose = Join-Path $script:Raiz 'compose.yaml'

    if (-not (Test-Path -LiteralPath $compose)) {
        throw "compose.yaml nao encontrado em $script:Raiz."
    }

    if ($RecriarBanco) {
        Escrever-Log -Nivel 'AVISO' -Mensagem 'Recriando o banco (todos os dados serao apagados)...'
        Invoke-Processo -Arquivo 'docker' -Argumentos @('compose', '-f', $compose, 'down', '-v') -Descricao 'docker compose down -v' | Out-Null
    }
    else {
        Garantir-ContainerLivre
    }

    Verificar-PortaPostgres

    Invoke-Processo -Arquivo 'docker' `
                   -Argumentos @('compose', '-f', $compose, 'up', '-d') `
                   -Descricao 'docker compose up -d' | Out-Null

    Escrever-Log -Nivel 'INFO' -Mensagem "Aguardando o container $NomeContainer ficar pronto..."

    $estadoAnterior = ''

    for ($i = 0; $i -lt 120; $i++) {
        $estado = Obter-EstadoContainer -Nome $NomeContainer

        if ($estado -eq 'healthy' -or $estado -eq 'running') {
            break
        }

        if ($i -eq 119) {
            Invoke-Processo -Arquivo 'docker' -Argumentos @('logs', '--tail', '40', $NomeContainer) -Descricao 'docker logs' -Silencioso
            throw "O container $NomeContainer nao ficou pronto. Veja os logs acima."
        }

        Start-Sleep -Seconds 2

        # So repete a mensagem quando o estado muda, para o log nao encher.
        if ($estado -ne $estadoAnterior) {
            Escrever-Log -Nivel 'INFO' -Mensagem "Estado do container: $estado ($($i + 1)s)"
            $estadoAnterior = $estado
        }
    }

    Escrever-Log -Nivel 'OK' -Mensagem "Container $NomeContainer pronto."
}

function Aplicar-Sql {
    Escrever-Passo '5/7  Inicializando o banco de dados'

    $scripts = New-Object System.Collections.Generic.List[object]

    $inicializacao = Join-Path $script:Raiz 'inicializacao.sql'

    if (-not (Test-Path -LiteralPath $inicializacao)) {
        throw "inicializacao.sql nao encontrado em $script:Raiz."
    }

    $scripts.Add(@{ Local = $inicializacao; Remoto = '/tmp/00_inicializacao.sql'; Origem = 'inicializacao.sql' })

    $extraSql = Resolver-Recurso 'sql\03_coluna_imagem.sql'

    if ($extraSql) {
        $scripts.Add(@{ Local = $extraSql; Remoto = '/tmp/03_coluna_imagem.sql'; Origem = '03_coluna_imagem.sql' })
    }

    # Copiar o arquivo para dentro do container preserva a codificacao UTF-8
    # (o PowerShell corromperia os acentos ao enviar texto pelo pipe).
    foreach ($item in $scripts) {
        Invoke-Processo -Arquivo 'docker' `
                       -Argumentos @('cp', $item.Local, "$($NomeContainer):$($item.Remoto)") `
                       -Descricao "docker cp $($item.Origem)" | Out-Null

        Invoke-Processo -Arquivo 'docker' `
                       -Argumentos @('exec', $NomeContainer, 'psql', '-U', $UsuarioBanco, '-d', $NomeBanco, '-v', 'ON_ERROR_STOP=1', '-f', $item.Remoto) `
                       -Descricao "psql -f $($item.Origem)" | Out-Null

        Escrever-Log -Nivel 'OK' -Mensagem "Aplicado: $($item.Origem)"
    }

    $coluna = Invoke-Capturar -Arquivo 'docker' -Argumentos @(
        'exec', $NomeContainer, 'psql', '-U', $UsuarioBanco, '-d', $NomeBanco, '-t', '-A', '-c',
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'usuarios' AND column_name = 'imagem';"
    )

    if ($coluna -match '1') {
        Escrever-Log -Nivel 'OK' -Mensagem 'Coluna usuarios.imagem (BYTEA) presente.'
    }
    else {
        throw 'A coluna usuarios.imagem nao foi criada. O cadastro e o reconhecimento facial nao funcionariam.'
    }

    $tabelas = Invoke-Capturar -Arquivo 'docker' -Argumentos @(
        'exec', $NomeContainer, 'psql', '-U', $UsuarioBanco, '-d', $NomeBanco, '-t', '-A', '-c',
        "SELECT string_agg(table_name, ', ') FROM information_schema.tables WHERE table_schema = 'public';"
    )

    Escrever-Log -Nivel 'OK' -Mensagem "Tabelas disponiveis: $tabelas"
}

function Preparar-Banco {
    if ($PularBanco) {
        Escrever-Log -Nivel 'AVISO' -Mensagem 'Etapa de banco ignorada (-PularBanco).'
        return
    }

    Iniciar-Docker
    Subir-Container
    Aplicar-Sql
}

# --------------------------------------------------------------------------
# Etapa 6 - Testes
# --------------------------------------------------------------------------

function Executar-Testes {
    param([string] $Python)

    Escrever-Passo '6/7  Executando a suite de testes'

    $pastaTestes = Join-Path $script:Raiz 'tests'

    if (-not (Test-Path -LiteralPath $pastaTestes)) {
        Escrever-Log -Nivel 'AVISO' -Mensagem "Pasta de testes nao encontrada em $pastaTestes."
        return
    }

    $env:PYTHONPATH = "$script:Raiz;$($script:Raiz)\src"

    Invoke-Processo -Arquivo $Python `
                   -Argumentos @('-m', 'unittest', 'discover', '-s', 'tests', '-t', '.') `
                   -Descricao 'python -m unittest discover' `
                   -CodigosAceitos @(0) `
                   -Pasta $script:Raiz | Out-Null

    Escrever-Log -Nivel 'OK' -Mensagem 'Testes concluidos.'
}

# --------------------------------------------------------------------------
# Etapa 7 - Inicializar a aplicacao
# --------------------------------------------------------------------------

function Porta-EmUso {
    param([int] $Porta)

    try {
        $conexao = New-Object System.Net.Sockets.TcpClient
        $tarefa = $conexao.ConnectAsync('127.0.0.1', $Porta)

        if ($tarefa.Wait(1500) -and $conexao.Connected) {
            $conexao.Close()
            return $true
        }

        $conexao.Close()
    }
    catch {
    }

    return $false
}

function Iniciar-Aplicacao {
    param([string] $Python)

    Escrever-Passo '7/7  Iniciando a aplicacao'

    if (Porta-EmUso -Porta $PortaApp) {
        Escrever-Log -Nivel 'AVISO' -Mensagem "A porta $PortaApp ja esta em uso. A aplicacao parece ja estar rodando."
        Escrever-Log -Nivel 'AVISO' -Mensagem "Abra $UrlApp no navegador. Para reiniciar, feche o processo que ocupa a porta."
        Abrir-Navegador
        return
    }

    $env:PYTHONPATH   = "$script:Raiz;$($script:Raiz)\src"
    $env:PYTHONUTF8   = '1'
    $env:PYTHONIOENCODING = 'utf-8'

    # Evita erro de codigo em nomes acentuados no console do Windows.
    try { chcp 65001 | Out-Null } catch { }

    $tarefaAbertura = $null

    if (-not $NaoAbrirNavegador) {
        $tarefaAbertura = Start-Job -ScriptBlock {
            param($url)

            for ($i = 0; $i -lt 180; $i++) {
                Start-Sleep -Seconds 1

                try {
                    $resposta = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3

                    if ($resposta.StatusCode -eq 200) {
                        Start-Process $url
                        return
                    }
                }
                catch {
                }
            }
        } -ArgumentList $UrlApp
    }

    Escrever-Log -Nivel 'OK' -Mensagem "API em $UrlApp  (Ctrl+C para encerrar)"
    Escrever-Log -Nivel 'INFO' -Mensagem "Log completo em: $script:LogPath"

    try {
        Push-Location -LiteralPath $script:Raiz

        & $Python -m src.main 2>&1 | ForEach-Object {
            $linha = [string]$_

            if (-not [string]::IsNullOrWhiteSpace($linha)) {
                Write-Host "    $linha" -ForegroundColor DarkGray
                Add-Content -LiteralPath $script:LogPath -Value "    $linha" -Encoding UTF8 -ErrorAction SilentlyContinue
            }
        }
    }
    finally {
        Pop-Location

        if ($tarefaAbertura) {
            Stop-Job -Job $tarefaAbertura -ErrorAction SilentlyContinue
            Remove-Job -Job $tarefaAbertura -Force -ErrorAction SilentlyContinue
        }

        Escrever-Log -Nivel 'AVISO' -Mensagem 'Aplicacao encerrada.'
    }
}

function Abrir-Navegador {
    if ($NaoAbrirNavegador) { return }

    try {
        Start-Process $UrlApp
        Escrever-Log -Nivel 'OK' -Mensagem "Navegador aberto em $UrlApp"
    }
    catch {
        Escrever-Log -Nivel 'AVISO' -Mensagem "Abra $UrlApp manualmente no navegador."
    }
}

# --------------------------------------------------------------------------
# Fluxo principal
# --------------------------------------------------------------------------

$codigoSaida = 0

try {
    Set-Content -LiteralPath $script:LogPath -Value '' -Encoding UTF8

    Bloquear-Execucao

    Escrever-Titulo 'VerdeID - instalador de dependencias e inicializacao'

    Escrever-Log -Nivel 'INFO' -Mensagem "Raiz do projeto: $script:Raiz"
    Escrever-Log -Nivel 'INFO' -Mensagem "Log da instalacao: $script:LogPath"
    Escrever-Log -Nivel 'INFO' -Mensagem "Python minimo: $NomePythonMinimo"

    $arquivosObrigatorios = @('requirements.txt', 'compose.yaml', 'inicializacao.sql', 'index.html', 'src\main.py')

    foreach ($arquivo in $arquivosObrigatorios) {
        if (-not (Test-Path -LiteralPath (Join-Path $script:Raiz $arquivo))) {
            throw "Estrutura do projeto incompleta: '$arquivo' nao encontrado em $script:Raiz."
        }
    }

    $python = Preparar-AmbienteVirtual

    if ($PularDependencias) {
        Escrever-Log -Nivel 'AVISO' -Mensagem 'Instalacao de dependencias ignorada (-PularDependencias).'
    }
    else {
        Instalar-Dependencias -Python $python
    }

    Preparar-Env
    Preparar-Banco

    if ($ExecutarTestes) {
        Executar-Testes -Python $python
    }

    if ($SomenteInstalar) {
        Escrever-Titulo 'Instalacao concluida'
        Escrever-Log -Nivel 'OK' -Mensagem 'Ambiente pronto. Use "InstaladorVerdeID.exe" sem -SomenteInstalar para iniciar a aplicacao.'
    }
    else {
        Iniciar-Aplicacao -Python $python
    }

    Escrever-Log -Nivel 'OK' -Mensagem 'Processo finalizado.'
}
catch {
    $codigoSaida = 1
    Escrever-Log -Nivel 'ERRO' -Mensagem $_.Exception.Message
    Escrever-Log -Nivel 'ERRO' -Mensagem "Detalhes em $script:LogPath"
}
finally {
    Liberar-Execucao

    Write-Host ''

    if ($ManterJanela -or $codigoSaida -ne 0) {
        # Se a entrada padrao estiver redirecionada (execucao por script ou
        # tarefa), nao ha console esperando: o ReadLine travaria para sempre.
        $interativo = $true

        try { $interativo = -not [Console]::IsInputRedirected } catch { }

        if ($interativo) {
            Write-Host 'Pressione ENTER para fechar esta janela...' -ForegroundColor DarkGray
            try { $null = Read-Host } catch { }
        }
    }
}

exit $codigoSaida