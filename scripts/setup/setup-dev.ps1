<#
.SYNOPSIS
Bootstrap / update dev environment

.DESCRIPTION
Written for pyenv, version 3.11.9
Usage:  .\scripts\dev.ps1

================================================

- run scripts by poetry run python scriptname.py

================================================

.NOTES
Change Log:
-

TODO:
add psycopg to this setup, doesnt work in poetry
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
} catch {
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
        } catch {
            try {
                Write-Verbose "[Poetry] Trying installation using 'py'"
                (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
                Write-Verbose "[Poetry] Successful!"
            } catch {
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
    } else {
        Write-Host "[Poetry] Poetry is already installed."
    }
    write-Host "----------------- Poetry Check complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[Poetry] An error ocurred during poetry installation $($_.InvocationInfo.ScriptLineNumber): `n$_"
    exit 1
}

# --- 3. install project dependencies ---
write-Host "`n----------------- Dependency Installation -----------------" -ForegroundColor Cyan
try {
    Write-Host "[Dependencies] Installing dependencies... "

    Write-Host "[Dependencies] Setting cuBLAS, cmake environment variables..."
    $env:CMAKE_ARGS="-DGGML_CUDA=ON -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release" # the -DGGML_CUDA flag enables CUDA support
    $env:FORCE_CMAKE=1

    $cudaVersion = (nvcc --version 2>$null) -match 'release \d+\.\d+' -replace '.*release (\d+\.\d+).*', '$1'
    if ([string]::IsNullOrEmpty($cudaVersion)) {
        Write-Warning "[Dependencies] CUDA not detected. LLM will run in CPU-only mode (much slower)."
        $env:CMAKE_ARGS="-DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release"
    } elseif ($cudaVersion -lt "11.6") {
        Write-Warning "[Dependencies] CUDA version $cudaVersion may be too old. Recommended: 11.8+"
        # we'll allow it to install with CUDA Support
    }

    try {
        poetry install --with dev
        poetry run pip install structlog
        poetry run pip install aioconsole
        Write-Host "[Dependencies] Installation complete." -ForegroundColor Green
    } catch {
        Write-Warning "[Dependencies] Failed to install all dependencies together. Trying runtime dependencies only..."
        poetry install --no-dev

        Write-Host "[Dependencies] Installing dev dependencies seperately..." -ForegroundColor Yellow
        poetry install --only dev
    }


    write-Host "----------------- Dependency installation complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[Dependencies] An error occured during dependency installation at line $($_.InvocationInfo.ScriptLineNumber):`n$_"

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
} catch {
    Write-Error "[Hooks] An error ocurred during hook initialization at line $($_.InvocationInfo.ScriptLineNumber): `n$_"

    Write-Host "`[Hooks] Checking pre-commit status:" -ForegroundColor Yellow
    try { poetry run pip show pre-commit } catch { Write-Host "pre-commit not installed" -ForegroundColor Red }
    Write-Host "`n[Hooks] Checking if .pre-commit-config.yaml exists: " -ForegroundColor Yellow
    if (Test-Path ".\.pre-commit-config.yaml") {
        Write-Host ".pre-commit-config.yaml found" -ForegroundColor Green
        Write-Host "$(Get-Content ".pre-commit-config.yaml" | Select-Object -First 10)`n..."
    } else {
        Write-Host ".pre-commit-config.yaml not found" -ForegroundColor Red
    }
    exit 1
}

# --- Check if piper-tts was installed correctly ---
write-Host "`n----------------- TTS Installation Verification -----------------" -ForegroundColor Cyan
# temporary script to 'poetry-run'
$piperCheckScript = @"
import sys
try:
    import piper
    from piper.voice import PiperVoice
    print(f"Piper TTS version: {piper.__version__ if hasattr(piper, '__version__') else 'unknown'}") # this check doesnt work yet
    print("Piper TTS module imported successfully")
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

        $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
        $piperCheckScript | Out-File -FilePath $tempScript -Encoding utf8

        try {
            Write-Host "[TTS] Testing piper-tts import..." -ForegroundColor Yellow
            poetry run python $tempScript
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[TTS] Success! piper-tts is properly installed." -ForegroundColor Green
            } else {
                Write-Warning "[TTS] piper-tts is installed but could not be imported properly."
                Write-Warning "[TTS] Will attempt to reinstall..."

                poetry run pip uninstall -y piper-tts

                # Install build tools first (often required for piper-tts on Windows)
                Write-Host "[TTS] Installing build dependencies..." -ForegroundColor Yellow
                poetry run pip install --upgrade pip setuptools wheel

                Write-Host "[TTS] Installing piper-tts manually..." -ForegroundColor Yellow
                poetry run pip install piper-tts --verbose

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

        Write-Host "[TTS] Installing build dependencies..." -ForegroundColor Yellow
        poetry run pip install --upgrade pip setuptools wheel

        try {
            Write-Host "[TTS] Uninstalling existing versions..."
            poetry run pip uninstall -y piper-tts piper-phonemize

            Write-Host "[TTS] Cleaning pip cache..."
            poetry run pip cache purge

            Write-Host "[TTS] Installing piper-tts..."
            poetry run pip install piper-phonemize-fix onnxruntime-gpu  --no-deps piper-tts # thanks to https://github.com/rhasspy/piper/issues/509

            Write-Host "[TTS] piper-tts installation completed" -ForegroundColor Green
        } finally {}

        $piperInstalled = poetry run pip list | Select-String "piper-tts"
        if ($piperInstalled) {
            Write-Host "[TTS] Manual installation of piper-tts succeeded. Verifying..." -ForegroundColor Green

            $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
            $piperCheckScript | Out-File -FilePath $tempScript -Encoding utf8

            try {
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[TTS] Success! piper-tts is properly installed." -ForegroundColor Green
                } else {
                    Write-Warning "[TTS] piper-tts is installed but could not be imported properly."
                    Write-Warning "[TTS] You might need to install Microsoft Visual C++ Build Tools."
                }
            } finally {
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

} catch {
    Write-Error "[TTS] An error occurred during TTS verification at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    Write-Warning "[TTS] Continuing with setup despite TTS verification failure."
}

# --- Check if faster-whisper installed correctly ---
write-Host "`n----------------- STT Installation Verification -----------------" -ForegroundColor Cyan
$whisperCheckScript = @"
import sys
try:
    import faster_whisper
    from faster_whisper import WhisperModel
    print(f"faster-whisper version: {faster_whisper.__version__ if hasattr(faster_whisper, '__version__') else 'unknown'}")
    print("faster-whisper module imported successfully")
    sys.exit(0)
except Exception as e:
    print(f"Error importing faster_whisper module: {e}")
    sys.exit(1)
"@

try {
    Write-Host "[STT] Checking if faster-whisper is installed..."
    $whisperInstalled = poetry run pip list | Select-String "faster-whisper"

    if ($whisperInstalled) {
        Write-Host "[STT] faster-whisper found in environment. Verifying..." -ForegroundColor Green
        $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
        $whisperCheckScript | Out-File -FilePath $tempScript -Encoding utf8

        try {
            Write-Host "[STT] Testing faster-whisper import..." -ForegroundColor Yellow
            poetry run python $tempScript
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[STT] Success! faster-whisper is properly installed." -ForegroundColor Green
            } else {
                Write-Warning "[STT] faster-whisper is installed but could not be imported properly."
                Write-Warning "[STT] Will attempt to reinstall..."

                Write-Host "[STT] Checking for required dependencies..." -ForegroundColor Yellow
                $ctTranslateInstalled = poetry run pip list | Select-String "ctranslate2"
                if (-not $ctTranslateInstalled) {
                    Write-Host "[STT] Installing ctranslate2 first..." -ForegroundColor Yellow
                    poetry run pip install ctranslate2==4.4.0 --no-cache-dir
                }

                poetry run pip uninstall -y faster-whisper

                Write-Host "[STT] Installing faster-whisper manually..." -ForegroundColor Yellow
                poetry run pip install faster-whisper==1.0.1 --no-cache-dir --verbose

                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[STT] Success! Manual installation of faster-whisper succeeded." -ForegroundColor Green
                } else {
                    Write-Warning "[STT] faster-whisper could not be properly installed."
                    Write-Warning "[STT] You might need to install additional dependencies."
                }
            }
        } finally {
            Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
        }
    } else {
        Write-Warning "[STT] faster-whisper not found in environment. Attempting manual installation..."
        Write-Host "[STT] Installing required dependencies..." -ForegroundColor Yellow
        poetry run pip install ctranslate2==4.4.0 --no-cache-dir

        Write-Host "[STT] Installing faster-whisper manually..." -ForegroundColor Yellow
        poetry run pip install faster-whisper==1.0.1 --no-cache-dir --verbose

        $whisperInstalled = poetry run pip list | Select-String "faster-whisper"
        if ($whisperInstalled) {
            Write-Host "[STT] Manual installation of faster-whisper succeeded. Verifying..." -ForegroundColor Green

            $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
            $whisperCheckScript | Out-File -FilePath $tempScript -Encoding utf8

            try {
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[STT] Success! faster-whisper is properly installed." -ForegroundColor Green
                } else {
                    Write-Warning "[STT] faster-whisper is installed but could not be imported properly."
                    Write-Warning "[STT] There might be issues with CUDA compatibility or missing dependencies."
                }
            } finally {
                Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
            }
        } else {
            Write-Error "[STT] Failed to install faster-whisper manually."
            Write-Warning "[STT] Common issues:"
            Write-Warning "[STT] 1. CUDA version incompatibility"
            Write-Warning "[STT] 2. Missing system dependencies"
            Write-Warning "[STT] 3. Conflicts with other packages"
        }
    }

    write-Host "----------------- STT Verification complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[STT] An error occurred during STT verification at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    Write-Warning "[STT] Continuing with setup despite STT verification failure."
}

# --- Check if pvporcupine was installed correctly ---
write-Host "`n----------------- Wake Word Installation Verification -----------------" -ForegroundColor Cyan

$porcupineCheckScript = @"
import sys
try:
    import pvporcupine
    print(f"pvporcupine version: {pvporcupine.LIBRARY_VERSION if hasattr(pvporcupine, 'LIBRARY_VERSION') else 'unknown'}")
    print("pvporcupine module imported successfully")

    # Check if we can access core functionality
    keywords = pvporcupine.KEYWORDS
    print(f"Available keywords: {len(keywords)}")
    sys.exit(0)
except Exception as e:
    print(f"Error importing pvporcupine module: {e}")
    sys.exit(1)
"@

try {
    Write-Host "[Wake] Checking if pvporcupine is installed..."
    $porcupineInstalled = poetry run pip list | Select-String "pvporcupine"

    if ($porcupineInstalled) {
        Write-Host "[Wake] pvporcupine found in environment. Verifying..." -ForegroundColor Green

        $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
        $porcupineCheckScript | Out-File -FilePath $tempScript -Encoding utf8

        try {
            Write-Host "[Wake] Testing pvporcupine import..." -ForegroundColor Yellow
            poetry run python $tempScript
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[Wake] Success! pvporcupine is properly installed." -ForegroundColor Green
            } else {
                Write-Warning "[Wake] pvporcupine is installed but could not be imported properly."
                Write-Warning "[Wake] Will attempt to reinstall..."

                poetry run pip uninstall -y pvporcupine

                Write-Host "[Wake] Installing pvporcupine manually..." -ForegroundColor Yellow
                poetry run pip install pvporcupine==3.0.0 --no-cache-dir --verbose

                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[Wake] Success! Manual installation of pvporcupine succeeded." -ForegroundColor Green
                } else {
                    Write-Warning "[Wake] pvporcupine could not be properly installed."
                    Write-Warning "[Wake] This may require a separate API key to use fully."
                }
            }
        } finally {
            Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
        }
    } else {
        Write-Warning "[Wake] pvporcupine not found in environment. Attempting manual installation..."
        Write-Host "[Wake] Installing pvporcupine manually..." -ForegroundColor Yellow
        poetry run pip install pvporcupine==3.0.0 --no-cache-dir --verbose

        $porcupineInstalled = poetry run pip list | Select-String "pvporcupine"
        if ($porcupineInstalled) {
            Write-Host "[Wake] Manual installation of pvporcupine succeeded. Verifying..." -ForegroundColor Green

            $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
            $porcupineCheckScript | Out-File -FilePath $tempScript -Encoding utf8

            try {
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[Wake] Success! pvporcupine is properly installed." -ForegroundColor Green
                } else {
                    Write-Warning "[Wake] pvporcupine is installed but could not be imported properly."
                    Write-Warning "[Wake] Note: To use pvporcupine fully, you may need an API key from Picovoice."
                }
            } finally {
                Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
            }
        } else {
            Write-Error "[Wake] Failed to install pvporcupine manually."
            Write-Warning "[Wake] Common issues:"
            Write-Warning "[Wake] 1. Network connectivity problems"
            Write-Warning "[Wake] 2. Python version incompatibility"
            Write-Warning "[Wake] 3. Missing system dependencies"
        }
    }

    write-Host "----------------- Wake Word Verification complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[Wake] An error occurred during Wake Word verification at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    Write-Warning "[Wake] Continuing with setup despite Wake Word verification failure."
}
read-host "Waiting for input to continue with LLM installation and build..."
# --- Check if llama-cpp-python was installed correctly with CUDA support ---
write-Host "`n----------------- LLM Installation Verification -----------------" -ForegroundColor Cyan
$tempScriptString = @"
import sys
try:
    import llama_cpp

    # Check if CUDA is available using a different approach
    has_cuda = False

    try:
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
    $llamaInstalled = poetry run pip list | Select-String "llama_cpp_python"

    if ($llamaInstalled) {
        Write-Host "[LLM] llama-cpp-python found in environment. Verifying CUDA support..." -ForegroundColor Green

        $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
        $tempScriptString | Out-File -FilePath $tempScript -Encoding utf8

        try {
            Write-Host "[LLM] Testing CUDA support..." -ForegroundColor Yellow
            poetry run python $tempScript
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[LLM] Success! llama-cpp-python has CUDA support." -ForegroundColor Green
            } else {
                Write-Warning "[LLM] llama-cpp-python is installed but CUDA support is not detected."
                Write-Warning "[LLM] Will attempt to reinstall with explicit CUDA flags..."

                Write-Host "[LLM] Using build flags:" -ForegroundColor Yellow
                Write-Host "  CMAKE_ARGS: $env:CMAKE_ARGS" -ForegroundColor Yellow
                Write-Host "  FORCE_CMAKE: $env:FORCE_CMAKE" -ForegroundColor Yellow

                poetry run pip uninstall -y llama-cpp-python
                poetry run pip install llama-cpp-python --no-cache-dir --verbose --upgrade --extra-index-url https://download.pytorch.org/whl/cu121

                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[LLM] Success! Manual installation of llama-cpp-python with CUDA succeeded." -ForegroundColor Green
                } else {
                    Write-Warning "[LLM] CUDA support could not be enabled. LLM will run on CPU only."
                    Write-Warning "[LLM] Check your CUDA installation and try again manually if needed."
                }
            }
        } finally {
            Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
        }
    } else {
        Write-Warning "[LLM] llama-cpp-python not found in environment. Attempting manual installation..."

        Write-Host "[LLM] Using build flags:" -ForegroundColor Yellow
        Write-Host "  CMAKE_ARGS: $env:CMAKE_ARGS" -ForegroundColor Yellow
        Write-Host "  FORCE_CMAKE: $env:FORCE_CMAKE" -ForegroundColor Yellow

        poetry run pip install llama-cpp-python --no-cache-dir --verbose --extra-index-url https://download.pytorch.org/whl/cu121

        $llamaInstalled = poetry run pip list | Select-String "llama_cpp_python"
        if ($llamaInstalled) {
            Write-Host "[LLM] Manual installation of llama-cpp-python succeeded. Checking CUDA support..." -ForegroundColor Green

            $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
            $tempScriptString | Out-File -FilePath $tempScript -Encoding utf8

            try {
                poetry run python $tempScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[LLM] Success! llama-cpp-python has CUDA support." -ForegroundColor Green
                } else {
                    Write-Warning "[LLM] llama-cpp-python is installed but CUDA support is not detected."
                    Write-Warning "[LLM] The LLM will run on CPU only, which will be much slower."
                }
            } finally {
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
    Write-Warning "[LLM] Continuing with setup despite LLM verification failure."
}

write-Host "`n================= Installation Summary =================" -ForegroundColor Cyan

# Create arrays to store component statuses
$components = @()
$components += [PSCustomObject]@{
    Component = "Python"
    Status = "Installed"
    Version = (python --version 2>&1).ToString().Replace("Python ", "")
    Notes = "Using pyenv with 3.11.9"
}

$components += [PSCustomObject]@{
    Component = "Poetry"
    Status = "Installed"
    Version = (poetry --version 2>&1).ToString().Replace("Poetry (version ", "").Replace(")", "")
    Notes = ""
}

$llamaInstalled = poetry run pip list | Select-String "llama_cpp_python"
$llamaVersion = if ($llamaInstalled) {
    ($llamaInstalled -split "\s+")[1]
} else {
    "Not installed"
}

$llamaCudaStatus = "Unknown"
if ($llamaInstalled) {
    # == LOOK AT == -> maybe we can reuse the script from above / create one for both
    $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
    $tempScriptString | Out-File -FilePath $tempScript -Encoding utf8

    try {
        poetry run python $tempScript 2>$null
        if ($LASTEXITCODE -eq 0) {
            $llamaCudaStatus = "CUDA"
        }
    } catch {
        $llamaCudaStatus = "Error checking"
    } finally {
        Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
    }
}

$components += [PSCustomObject]@{
    Component = "LLM (llama-cpp-python)"
    Status = if ($llamaInstalled) { "Installed" } else { "Failed" }
    Version = $llamaVersion
    Notes = "Backend: $llamaCudaStatus"
}

$piperInstalled = poetry run pip list | Select-String "piper-tts"
$piperVersion = if ($piperInstalled) {
    ($piperInstalled -split "\s+")[1]
} else {
    "Not installed"
}

$piperStatus = "Unknown"
if ($piperInstalled) {
    $tempScript = [System.IO.Path]::GetTempFileName() + ".py"
    @"
import sys
try:
    import piper
    print("OK")
    sys.exit(0)
except:
    print("ERROR")
    sys.exit(1)
"@ | Out-File -FilePath $tempScript -Encoding utf8

    try {
        $piperStatus = poetry run python $tempScript 2>$null
    } catch {
        $piperStatus = "Error checking"
    } finally {
        Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
    }
}

$components += [PSCustomObject]@{
    Component = "TTS (piper-tts)"
    Status = if ($piperInstalled) { "Installed" } else { "Failed" }
    Version = $piperVersion
    Notes = "Import: $piperStatus"
}

$fastWhisperInstalled = poetry run pip list | Select-String "faster-whisper"
$fastWhisperVersion = if ($fastWhisperInstalled) {
    ($fastWhisperInstalled -split "\s+")[1]
} else {
    "Not installed"
}

$components += [PSCustomObject]@{
    Component = "STT (faster-whisper)"
    Status = if ($fastWhisperInstalled) { "Installed" } else { "Failed" }
    Version = $fastWhisperVersion
    Notes = ""
}

$porcupineInstalled = poetry run pip list | Select-String "pvporcupine"
$porcupineVersion = if ($porcupineInstalled) {
    ($porcupineInstalled -split "\s+")[1]
} else {
    "Not installed"
}

$components += [PSCustomObject]@{
    Component = "Wake Word (pvporcupine)"
    Status = if ($porcupineInstalled) { "Installed" } else { "Failed" }
    Version = $porcupineVersion
    Notes = ""
}

Write-Host
$components | ForEach-Object {
    $color = switch ($_.Status) {
        "Installed" { "Green" }
        "Failed" { "Red" }
        default { "Yellow" }
    }

    Write-Host ("{0,-25}" -f $_.Component) -NoNewline
    Write-Host ("{0,-10}" -f $_.Status) -ForegroundColor $color -NoNewline
    Write-Host ("{0,-15}" -f $_.Version) -NoNewline
    Write-Host $_.Notes
}

$issues = @()

if ($llamaCudaStatus -ne "CUDA") {
    $issues += "LLM may be running in CPU-only mode, which will be much slower"
}

if ($piperStatus -ne "OK") {
    $issues += "piper-tts import failed, which might prevent text-to-speech functionality"
}

if (-not $fastWhisperInstalled) {
    $issues += "faster-whisper is not installed, which will prevent speech recognition"
}

if ($issues.Count -gt 0) {
    Write-Host "`nPotential Issues:" -ForegroundColor Yellow
    foreach ($issue in $issues) {
        Write-Host " - $issue" -ForegroundColor Yellow
    }
}

Write-Host "`nEnvironment Information:" -ForegroundColor Cyan
Write-Host " - CUDA Version: $((nvcc --version 2>$null) -match 'release \d+\.\d+' -replace '.*release (\d+\.\d+).*', '$1')"
Write-Host " - GPU: $((Get-WmiObject Win32_VideoController).Name -join ', ')"
Write-Host " - Poetry Environment: $(poetry env info -p)"
Write-Host " - Free Disk Space: $([math]::Round((Get-PSDrive -Name C).Free / 1GB, 2)) GB"

Write-Host "============ Setup completed. ============" -ForegroundColor Green
