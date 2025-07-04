<#
.SYNOPSIS
Download a GGUF model for testing

.DESCRIPTION
This script downloads a small GGUF model for testing purposes.
#>

$ErrorActionPreference = "Stop"

# Create models directory if it doesn't exist
$modelsDir = "$PSScriptRoot\models"
if (-not (Test-Path $modelsDir)) {
    New-Item -ItemType Directory -Path $modelsDir | Out-Null
}

# Set the model URL and destination path
$modelUrl = "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
$modelPath = "$modelsDir\tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

# Download the model if it doesn't exist
if (-not (Test-Path $modelPath)) {
    Write-Host "Downloading test model (TinyLlama 1.1B)..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath
    Write-Host "Model downloaded to $modelPath" -ForegroundColor Green
} else {
    Write-Host "Model already exists at $modelPath" -ForegroundColor Green
}
