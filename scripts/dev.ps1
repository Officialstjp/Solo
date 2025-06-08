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
write-Host "------- Python Check --------" -ForegroundColor Cyan
try {
    if (-not (pyenv versions | Select-String "3.11")) {
        write-host "    [Python Check] Python 3.11 not found, will be installed..."
        pyenv install 3.11.9
    } else {
        write-host "    [Python Check] Python 3.11 found!"
    }
    Write-Verbose "    [Python Check] Setting Pyenv to 3.11.9.."
    pyenv local 3.11.9
    write-Host "------- Python Check complete -------" -ForegroundColor Green
}
catch {
    Write-Error "[Python Check] An error ocurred during at line $($_.InvocationInfo.ScriptLineNumber): `n$_"
    exit 1
}

# --- 2. Install poetry in the venv ---
write-Host "`n------- Poetry Installation Check--------" -ForegroundColor Cyan
try {
    if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
        Write-Host "    [Poetry] Installing poetry... "
        try {
            Write-Verbose "    [Poetry] Trying installation using 'python'"
            (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
            Write-Verbose "    [Poetry] Successful!"
        }
        catch {
            try {
                Write-Verbose "    [Poetry] Trying installation using 'py'"
                (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
                Write-Verbose "    [Poetry] Successful!"
            }
            catch {
                Write-Error "[Poetry] Couldn't fetch poetry installer script.: `n$_"
            }
        }
        $currentUser = $env:USERNAME
        $pythonScriptsPath = "C:\Users\$currentUser\AppData\Roaming\Python\Scripts"

        Write-Verbose "    [Poetry] Checking for Python\Scripts in environment variable..."
        if ($([Environment]::GetEnvironmentVariable("Path", "User")) -notmatch [regex]::Escape($pythonScriptsPath)) {
            Write-Host "    [Poetry] Adding Python\Scripts directory to PATH: $pythonScriptsPath" -ForegroundColor Yellow
            [Environment]::SetEnvironmentVariable(
                "Path",
                [Environment]::GetEnvironmentVariable("Path", "User") + ";$pythonScriptsPath",
                "User"
            )
            Write-Host "    [Poetry] Path updated. You may need to restart your terminal for changes to take effect." -ForegroundColor Yellow
        } else {
            Write-Verbose "    [Poetry] Python\Scripts directory already in PATH"
        }
    }
    else {
        Write-Host "    [Poetry] Poetry is already installed."
    }
    write-Host "------- Poetry Check complete -------" -ForegroundColor Green
}
catch {
    Write-Error "[Poetry] An error ocurred during poetry installation $($_.InvocationInfo.ScriptLineNumber): `n$_"
    exit 1
}

# --- 3. install project dependencies ---
write-Host "`n------- Dependency Installation --------" -ForegroundColor Cyan
try {
    Write-Host "    [Dependencies] Installing dependencies... "
    poetry install --with dev
    write-Host "------- Dependency installation complete -------" -ForegroundColor Green
}
catch {
    Write-Error "[Dependencies] An error occured during dependency insitallation at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    exit 1
}

# --- 4. install Git hooks ---
write-Host "`n------- hooks Installation --------" -ForegroundColor Cyan
try {
    Write-Host "    [hooks] installing Git hooks"
    poetry run pre-commit install
    write-Host "------- hook installation complete -------" -ForegroundColor Green
}
catch {
    Write-Error "[hooks] An error ocurred during hook initialization at line $($_.InvocationInfo.ScriptLineNumber): `n$_"
    exit 1
}

Write-Host "============ Setup completed successfully! ============" -ForegroundColor Green
