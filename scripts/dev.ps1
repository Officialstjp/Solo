<#
.SYNOPSIS 
Bootstrap / update dev environment

.DESCRIPTION
Written for pyenv, version 3.11.9
Usage:  .\scripts\dev.ps1

================================================

Consider switching to Poetry Virtual Environments
- run scripts by poetry run python scriptname.py

================================================

.NOTES
Change Log:
-

#>
Write-Host "============ Environment Setup ============" -ForegroundColor Green
# --- 1. Ensure a valid python version is installed (3.11)---
try { 
    if (-not (python -m pyenv versions | Select-String "3.11")) {
        write-host "[1. Python Validation] Python 3.11 not found, will be installed..." -ForegroundColor Cyan
        python -m pyenv install 3.11.9
    }   
    python -m pyenv local 3.11.9
}
catch {
    Write-Error "[1. Python Validation] An error ocurred at line $($_.InvocationInfo.ScriptLineNumber) during setup: $_"
    exit 1
}
# --- 2. create venv if missing ---
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "[2. venv] Creating python virtual environment..." -ForegroundColor Cyan
        python -m venv .venv
    }    
}
catch {
    Write-Error "[2. venv] An error ocurred at line $($_.InvocationInfo.ScriptLineNumber) during setup: $_"
    exit 1
}

# --- 3. Activate ---
try {
    Write-Host "[3. Activation] Activating Virtual Envrionment... " -ForegroundColor Cyan
    & .\.venv\scripts\Activate.ps1
}    
catch {
    Write-Error "[3. Activation] An error ocurred at line $($_.InvocationInfo.ScriptLineNumber) during setup: $_"
    exit 1
}

# --- 4. Install poetry in the venv ---
try {
    if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
        Write-Host "[4. Install poetry] Installing poetry... " -ForegroundColor Cyan
        python -m pip install poetry
    }
}    
catch {
    Write-Error "[4. Install poetry] An error ocurred at line $($_.InvocationInfo.ScriptLineNumber) during setup: $_"
    exit 1
}

# --- 5. install project dependencies ---
try {
    Write-Host "5. Dependency installation] Installing dependencies... " -ForegroundColor Cyan
    python -m poetry install --with dev
}    
catch {
    Write-Error "[5. Dependency installation] An error at line $($_.InvocationInfo.ScriptLineNumber) Ocurred during setup: $_"
    exit 1
}

# --- 6. install Git hooks ---
try {
    Write-Host "[6. Hook initialization] installing Git hooks" -ForegroundColor Cyan
    python -m poetry run pre-commit install
}    
catch {
    Write-Error "[6. Hook initialization] An error ocurred at line $($_.InvocationInfo.ScriptLineNumber) during setup: $_"
    exit 1
}

Write-Host "============ Setup completed successfully! ============" -ForegroundColor Green