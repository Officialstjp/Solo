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

    Write-Host "[Dependencies] Setting cuBLAS, cmake environment variables..."
    $env:CMAKE_ARGS="-DGGML_CUDA=ON -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release"
    $env:FORCE_CMAKE=1

    try {
        poetry install --with dev
        Write-Host "[Dependencies] Installation complete." -ForegroundColor Green
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
# --- Check if llama-cpp-python was installed correctly with CUDA support ---
write-Host "`n----------------- LLM Installation Verification -----------------" -ForegroundColor Cyan
$tempScriptString = @"
import sys
try:
    import llama_cpp

    # Check if CUDA is available using a different approach
    has_cuda = False

    # Method 1: Try to create a model with CUDA flags and see if it works
    try:
        # Just create a small dummy context to test
        params = llama_cpp.llama_model_default_params()
        params.n_gpu_layers = 1  # Try to use GPU

        # Print CUDA-related environment info
        print(f"Using llama_cpp version: {llama_cpp.__version__ if hasattr(llama_cpp, '__version__') else 'unknown'}")
        print(f"CUDA support should be available: {llama_cpp.llama_supports_gpu_offload()}")

        has_cuda = llama_cpp.llama_supports_gpu_offload()
        print(f"CUDA support detected: {has_cuda}")

    except Exception as e:
        print(f"Error checking CUDA support: {e}")

    sys.exit(0 if has_cuda else 1)

except Exception as e:
    print(f"Error loading llama_cpp module: {e}")
    sys.exit(2)
"@

try {
    Write-Host "[LLM] Checking if llama-cpp-python is installed..."
    $llamaInstalled = poetry run pip list | Select-String "llama-cpp-python"

    if ($llamaInstalled) {
        Write-Host "[LLM] llama-cpp-python found in environment. Verifying CUDA support..." -ForegroundColor Green

        # Create a temporary Python script to check CUDA support
        $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
        $tempscriptString | Out-File -FilePath $tempScript -Encoding utf8

        # Run the script to check CUDA support
        try {
            Write-Host "[LLM] Testing CUDA support..." -ForegroundColor Yellow
            poetry run python $tempScript
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[LLM] Success! llama-cpp-python has CUDA support." -ForegroundColor Green
            } else {
                Write-Warning "[LLM] llama-cpp-python is installed but CUDA support is not detected."
                Write-Warning "[LLM] Will attempt to reinstall with explicit CUDA flags..."

                # Print the flags being used
                Write-Host "[LLM] Using build flags:" -ForegroundColor Yellow
                Write-Host "  CMAKE_ARGS: $env:CMAKE_ARGS" -ForegroundColor Yellow
                Write-Host "  FORCE_CMAKE: $env:FORCE_CMAKE" -ForegroundColor Yellow

                # Try manual installation with explicit flags
                poetry run pip uninstall -y llama-cpp-python
                poetry run pip install llama-cpp-python --no-cache-dir --verbose --upgrade --extra-index-url https://download.pytorch.org/whl/cu121

                # Check again after reinstallation
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[LLM] Success! Manual installation of llama-cpp-python with CUDA succeeded." -ForegroundColor Green
                } else {
                    Write-Warning "[LLM] CUDA support could not be enabled. LLM will run on CPU only."
                    Write-Warning "[LLM] Check your CUDA installation and try again manually if needed."
                }
            }
        } finally {
            # Clean up temporary script
            Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
        }
    } else {
        Write-Warning "[LLM] llama-cpp-python not found in environment. Attempting manual installation..."

        # Print the flags being used
        Write-Host "[LLM] Using build flags:" -ForegroundColor Yellow
        Write-Host "  CMAKE_ARGS: $env:CMAKE_ARGS" -ForegroundColor Yellow
        Write-Host "  FORCE_CMAKE: $env:FORCE_CMAKE" -ForegroundColor Yellow

        # Try manual installation
        poetry run pip install llama-cpp-python --no-cache-dir --verbose --extra-index-url https://download.pytorch.org/whl/cu121

        # Verify installation
        $llamaInstalled = poetry run pip list | Select-String "llama_cpp_python"
        if ($llamaInstalled) {
            Write-Host "[LLM] Manual installation of llama-cpp-python succeeded. Checking CUDA support..." -ForegroundColor Green

            # Create temporary script again to check CUDA support
            $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
            $tempscriptString | Out-File -FilePath $tempScript -Encoding utf8

            try {
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[LLM] Success! llama-cpp-python has CUDA support." -ForegroundColor Green
                } else {
                    Write-Warning "[LLM] llama-cpp-python is installed but CUDA support is not detected."
                    Write-Warning "[LLM] The LLM will run on CPU only, which will be much slower."
                }
            } finally {
                # Clean up temporary script
                Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
            }
        } else {
            Write-Error "[LLM] Failed to install llama-cpp-python manually."
            Write-Error "[LLM] Please try installing it manually with appropriate CUDA flags."
        }
    }

    write-Host "----------------- LLM Verification complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[LLM] An error occurred during LLM verification at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    # Continue with the script despite LLM verification failure
    Write-Warning "[LLM] Continuing with setup despite LLM verification failure."
}


# --- Check if piper-tts was installed correctly ---
write-Host "`n----------------- TTS Installation Verification -----------------" -ForegroundColor Cyan

$pipperCheckScript = @"
import sys
try:
    import piper
    from piper.voice import PiperVoice
    print(f"Piper TTS version: {piper.__version__ if hasattr(piper, '__version__') else 'unknown'}")
    print("Piper TTS module imported successfully")
    # No need to initialize a voice which would require model files
    # Just checking if the module is importable
    sys.exit(0)
except Exception as e:
    print(f"Error importing piper module: {e}")
    sys.exit(1)
"@

try {
    Write-Host "[TTS] Checking if piper-tts is installed..."
    $piperInstalled = poetry run pip list | Select-String "piper-tts"

    if ($piperInstalled) {
        Write-Host "[TTS] piper-tts found in environment. Verifying..." -ForegroundColor Green

        # Create a temporary Python script to check piper-tts
        $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
        $pipperCheckScript | Out-File -FilePath $tempScript -Encoding utf8

        # Run the script to check piper-tts
        try {
            Write-Host "[TTS] Testing piper-tts import..." -ForegroundColor Yellow
            poetry run python $tempScript
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[TTS] Success! piper-tts is properly installed." -ForegroundColor Green
            } else {
                Write-Warning "[TTS] piper-tts is installed but could not be imported properly."
                Write-Warning "[TTS] Will attempt to reinstall..."

                # Try manual installation
                poetry run pip uninstall -y piper-tts

                # Install build tools first (often required for piper-tts on Windows)
                Write-Host "[TTS] Installing build dependencies..." -ForegroundColor Yellow
                poetry run pip install --upgrade pip setuptools wheel

                # Try to install piper-tts manually
                Write-Host "[TTS] Installing piper-tts manually..." -ForegroundColor Yellow
                poetry run pip install piper-tts --verbose

                # Check again after reinstallation
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[TTS] Success! Manual installation of piper-tts succeeded." -ForegroundColor Green
                } else {
                    Write-Warning "[TTS] piper-tts could not be properly installed."
                    Write-Warning "[TTS] You might need to install Microsoft Visual C++ Build Tools."
                }
            }
        } finally {
            # Clean up temporary script
            Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
        }
    } else {
        Write-Warning "[TTS] piper-tts not found in environment. Attempting manual installation..."

        # Install build tools first (often required for piper-tts on Windows)
        Write-Host "[TTS] Installing build dependencies..." -ForegroundColor Yellow
        poetry run pip install --upgrade pip setuptools wheel

        # Try manual installation
        Write-Host "[TTS] Installing piper-tts manually..." -ForegroundColor Yellow
        poetry run pip install piper-tts --verbose

        # Verify installation
        $piperInstalled = poetry run pip list | Select-String "piper-tts"
        if ($piperInstalled) {
            Write-Host "[TTS] Manual installation of piper-tts succeeded. Verifying..." -ForegroundColor Green

            # Create temporary script again to check installation
            $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
            $pipperCheckScript | Out-File -FilePath $tempScript -Encoding utf8

            try {
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[TTS] Success! piper-tts is properly installed." -ForegroundColor Green
                } else {
                    Write-Warning "[TTS] piper-tts is installed but could not be imported properly."
                    Write-Warning "[TTS] You might need to install Microsoft Visual C++ Build Tools."
                }
            } finally {
                # Clean up temporary script
                Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
            }
        } else {
            Write-Error "[TTS] Failed to install piper-tts manually."
            Write-Warning "[TTS] Common issues on Windows:"
            Write-Warning "[TTS] 1. Missing Microsoft Visual C++ 14.0 or later"
            Write-Warning "[TTS] 2. Missing build tools (try: npm install --global windows-build-tools)"
            Write-Warning "[TTS] 3. Check for specific error messages in the output above"
        }
    }

    write-Host "----------------- TTS Verification complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[TTS] An error occurred during TTS verification at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    # Continue with the script despite TTS verification failure
    Write-Warning "[TTS] Continuing with setup despite TTS verification failure."
}

Write-Host "============ Setup completed successfully! ============" -ForegroundColor Green
