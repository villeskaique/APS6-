#Requires -Version 5.1

<#
    Gera o executavel InstaladorVerdeID.exe a partir de:
      - InstaladorVerdeID.cs  (launcher)
      - instalar.ps1          (logica de instalacao, embutida como recurso)

    Basta rodar:  powershell -ExecutionPolicy Bypass -File compilar.ps1
#>

[CmdletBinding()]
param(
    [string] $Saida
)

$ErrorActionPreference = 'Stop'

$baseDir   = $PSScriptRoot
$cs        = Join-Path $baseDir 'InstaladorVerdeID.cs'
$ps1       = Join-Path $baseDir 'instalar.ps1'

if (-not $Saida) {
    $Saida = Join-Path $baseDir 'InstaladorVerdeID.exe'
}

foreach ($obrigatorio in @($cs, $ps1)) {
    if (-not (Test-Path -LiteralPath $obrigatorio)) {
        throw "Arquivo nao encontrado: $obrigatorio"
    }
}

$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'

if (-not (Test-Path -LiteralPath $csc)) {
    throw "Compilador do .NET Framework nao encontrado em $csc"
}

if (Test-Path -LiteralPath $Saida) {
    Remove-Item -LiteralPath $Saida -Force
}

Write-Host "Compilando $Saida ..." -ForegroundColor Cyan

# O recurso "Instalador.Script" guarda o installing.ps1 dentro do executavel.
$argumentos = @(
    '/nologo'
    '/target:exe'
    '/optimize+'
    '/platform:anycpu'
    '/reference:System.dll'
    "/out:$Saida"
    "/resource:$ps1,Instalador.Script"
    $cs
)

& $csc @argumentos

if ($LASTEXITCODE -ne 0) {
    throw "Falha na compilacao (codigo $LASTEXITCODE)."
}

$info = Get-Item -LiteralPath $Saida

Write-Host ''
Write-Host "Gerado: $($info.FullName)  ($([math]::Round($info.Length / 1KB, 1)) KB)" -ForegroundColor Green
Write-Host 'Uso: clique duas vezes no .exe ou execute direto no PowerShell.'