$ErrorActionPreference = 'Stop'

Set-Location -LiteralPath $PSScriptRoot

Write-Host '=== AI Viral Shorts Generator ==='
Write-Host ''

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host '[ERROR] Python is not installed or not on PATH.'
    Write-Host 'Install Python 3.11+ from https://www.python.org/downloads/ and re-run this file.'
    Read-Host 'Press Enter to exit'
    exit 1
}

$ffmpegCandidates = @(
    "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffmpeg.exe"
)

$ffmpeg = $null
foreach ($candidate in $ffmpegCandidates) {
    if (Test-Path -LiteralPath $candidate) {
        $ffmpeg = $candidate
        break
    }
}

if (-not $ffmpeg) {
    $ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffmpegCommand) {
        $ffmpeg = $ffmpegCommand.Source
    }
}

if (-not $ffmpeg) {
    Write-Host '[ERROR] ffmpeg is not installed or not on PATH.'
    Write-Host 'Install with: winget install ffmpeg'
    Write-Host 'Or download from https://www.gyan.dev/ffmpeg/builds/ and add bin\ to PATH.'
    Read-Host 'Press Enter to exit'
    exit 1
}

$env:PATH = "$(Split-Path -Parent $ffmpeg);$env:PATH"

$venvPython = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host '[setup] Creating virtual environment in .venv\ ...'
    & $python.Path -m venv .venv
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host '[ERROR] Failed to create venv.'
    Read-Host 'Press Enter to exit'
    exit 1
}

if (-not (Test-Path -LiteralPath "$PSScriptRoot\.venv\.installed")) {
    Write-Host '[setup] Installing dependencies (one-time, ~2 min) ...'
    & $venvPython -m pip install --upgrade pip | Out-Null
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] pip install failed.'
        Read-Host 'Press Enter to exit'
        exit $LASTEXITCODE
    }
    New-Item -ItemType File -Path "$PSScriptRoot\.venv\.installed" -Force | Out-Null
}

if (-not (Test-Path -LiteralPath "$PSScriptRoot\.env")) {
    Write-Host ''
    Write-Host '[setup] No .env file found.'
    $gemKey = Read-Host 'Paste your Gemini API key (from https://aistudio.google.com/app/apikey)'
    Set-Content -LiteralPath "$PSScriptRoot\.env" -Value "GEMINI_API_KEY=$gemKey"
    Write-Host '[setup] Saved to .env'
}

Write-Host ''
Write-Host '=== Launching UI at http://localhost:5173 ==='
Write-Host 'Close this window to stop the server.'
Write-Host ''

Start-Process 'http://localhost:5173'
& $venvPython -m uvicorn src.web.app:app --host 127.0.0.1 --port 5173 --reload