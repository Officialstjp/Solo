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
Write-Host "================= Environment Setup =================" -ForegroundColor Green
# --- 1. Ensure a valid python version is installed (3.11)---
write-Host "----------------- Python Check -----------------" -ForegroundColor Cyan
try {
    if (-not (pyenv versions | Select-String "3.11")) {
        write-host "[Python Check] Python 3.11 not found, will be installed..."
        pyenv install 3.11.9
    } else {
        write-host "[Python Check] Python 3.11 found!"
    }
    Write-Verbose "[Python Check] Setting Pyenv to 3.11.9.."
    pyenv local 3.11.9
    write-Host "----------------- Python Check complete -----------------" -ForegroundColor Green
}
catch {
    Write-Error "[Python Check] An error ocurred during at line $($_.InvocationInfo.ScriptLineNumber): `n$_"
    exit 1
}

# --- 2. Install poetry in the venv ---
write-Host "`n----------------- Poetry Installation Check -----------------" -ForegroundColor Cyan
try {
    if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
        Write-Host "[Poetry] Installing poetry... "
        try {
            Write-Verbose "[Poetry] Trying installation using 'python'"
            (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
            Write-Verbose "[Poetry] Successful!"
        }
        catch {
            try {
                Write-Verbose "[Poetry] Trying installation using 'py'"
                (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
                Write-Verbose "[Poetry] Successful!"
            }
            catch {
                Write-Error "[Poetry] Couldn't fetch poetry installer script.: `n$_"
            }
        }
        $currentUser = $env:USERNAME
        $pythonScriptsPath = "C:\Users\$currentUser\AppData\Roaming\Python\Scripts"

        Write-Verbose "[Poetry] Checking for Python\Scripts in environment variable..."
        if ($([Environment]::GetEnvironmentVariable("Path", "User")) -notmatch [regex]::Escape($pythonScriptsPath)) {
            Write-Host "[Poetry] Adding Python\Scripts directory to PATH: $pythonScriptsPath" -ForegroundColor Yellow
            [Environment]::SetEnvironmentVariable(
                "Path",
                [Environment]::GetEnvironmentVariable("Path", "User") + ";$pythonScriptsPath",
                "User"
            )
            Write-Host "[Poetry] User PATH updated." -ForegroundColor Yellow
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
            Write-Host "[Poetry] Session PATH updated"
        } else {
            Write-Verbose "[Poetry] Python\Scripts directory already in PATH"
        }
    }
    else {
        Write-Host "[Poetry] Poetry is already installed."
    }
    write-Host "----------------- Poetry Check complete -----------------" -ForegroundColor Green
}
catch {
    Write-Error "[Poetry] An error ocurred during poetry installation $($_.InvocationInfo.ScriptLineNumber): `n$_"
    exit 1
}

# --- 3. install project dependencies ---
write-Host "`n----------------- Dependency Installation -----------------" -ForegroundColor Cyan
try {
    Write-Host "[Dependencies] Installing dependencies... "

    try {
        poetry install --with dev
        Write-Host "[Dependencies] All dependencies installed successfully" -ForegroundColor Green
    }
    catch {
        Write-Warning "[Dependencies] Failed to install all dependencies together. Trying runtime dependencies only..."

        poetry install --no-dev

        Write-Host "[Dependencies] Installing dev dependencies seperately..." -ForegroundColor Yellow
        poetry install --only dev

    }

    write-Host "----------------- Dependency installation complete -----------------" -ForegroundColor Green
}
catch {
    Write-Error "[Dependencies] An error occured during dependency insitallation at line $($_.InvocationInfo.ScriptLineNumber):`n$_"

    Write-Host "`n[Dependencies] Checking Poetry environment:" -ForegroundColor Yellow
    poetry env info
    Write-Host "`n[Dependencies] Listing available packages:" -ForegroundColor Yellow
    poetry show
    exit 1
}

# --- 4. install Git hooks ---
write-Host "`n------- Hooks Installation --------" -ForegroundColor Cyan
try {
    Write-Host "[Hooks] installing Git hooks"
    $precommitInstalled = poetry run pip list | select-String "pre_commit"
    if (-not $precommitInstalled) { $precommitInstalled = poetry run pip list | select-String "pre-commit"}

    if (-not $precommitInstalled) {
        Write-Warning "[Hooks] pre-commit not found in the environment. Installing manually..."
        poetry run pip install pre-commit
    }

    Write-Host "[Hooks] Installing Git hooks"
    poetry run pre-commit install
    write-Host "------- hook installation complete -------" -ForegroundColor Green
}
catch {
    Write-Error "[Hooks] An error ocurred during hook initialization at line $($_.InvocationInfo.ScriptLineNumber): `n$_"

    Write-Host "`[Hooks] Checking pre-commit status:" -ForegroundColor Yellow
    try { poetry run pip show pre-commit } catch { Write-Host "pre-commit not installed" -ForegroundColor Red }
    Write-Host "`n[Hooks] Checking if .pre-commit-config.yaml exists: " -ForegroundColor Yellow
    if (Test-Path ".\.pre-commit-config.yaml") {
        Write-Host ".pre-commit-config.yaml found" -ForegroundColor Green
        Write-Host "$(Get-Content ".pre-commit-config.yaml" | Select-Object -First 10)`n..."
    }
    else {
        Write-Host ".pre-commit-config.yaml not found" -ForegroundColor Red
    }
    exit 1
}

Write-Host "============ Setup completed successfully! ============" -ForegroundColor Green
