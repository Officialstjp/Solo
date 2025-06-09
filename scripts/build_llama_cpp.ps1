<#
.SYNOPSIS
Build llama.cpp with CUDA support on Windows

.DESCRIPTION
This script clones llama.cpp repository and builds it with cuBLAS support.
Requirements:
- Git
- CMake
- Cuda Toolkit
- Visual Studio 2019 or newer with C++ build tools

.EXAMPLE
.\scripts\build_llama_cpp.ps1

.NOTES
Change Log:
-
#>

$ErrorActionPreference = "Stop"

# Check for required tools
function Check-RequiredTools {
    Write-Host "Checking required tools..." -ForegroundColor Cyan

    $tools = @(
        @{Name = "git"; Command = "git --version"},
        @{Name = "cmake"; Command = "cmake --version"},
        @{Name = "CUDA"; Command = "nvcc --version"}
    )

    $allFound = $true

    foreach ($tool in $tools) {
        Write-Host "Checking for $($tool.Name)..." -NoNewline
        try {
            $output = Invoke-Expression $tool.Command 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Found: $output" -ForegroundColor Green
            } else {
                Write-Host "Didn't find tools '$($tool.name)': $output" -ForegroundColor Red
                $allFound = $false
            }
        } catch {
            Write-Host "Not found!" -ForegroundColor Red
            $allFound = $false
        }
    }

    if (-not $allfound) {
        Write-Error "One or more required tools are missing. Please install them before proceding."
        exit 1
    }
}

function Build-LlamaCpp {
    $repoDir = "llama.cpp"
    $buildDir = "$repoDir\build"

    if (-not (Test-Path $repoDir)) {
        Write-Host "Cloning llama.cpp repository..." -ForegroundColor Cyan
        git clone https://github.com/ggerganov/llama.cpp.git
    } else {
        Write-Host "Updating llama.cpp repository..." -ForegroundColor Cyan
        Push-Location $repoDir
        git pull
        Pop-Location
    }

    # create build directory
    if (-not (Test-Path $buildDir)) {
        New-Item -ItemType Directory -Path $buildDir | Out-Null
    }

    # build with CMake
    Write-Host "Building llama.cpp with CUDA support..." -ForegroundColor Cyan
    Push-Location $buildDir

    # Configure with CMake
    Write-Host "Configure CMake..." -ForegroundColor Cyan
    cmake .. -DLLAMA_CUBLAS=ON -DCMAKE_BUILD_TYPE=Release

    # Build
    Write-Host "Building..." -ForegroundColor Cyan
    cmake --build . --config Release

    Pop-Location

    # Check if build was successful
    if (Test-Path "$buildDir\bin\Release\main.exe") {
        Write-Host "build succesfull!" -ForegroundColor Green
        Write-Host "Binary location: $buildDir\bin\Release\main.exe" -ForegroundColor Green
    } else {
        Write-Error "Build failed! Check the logs for more information"
        exit 1
    }
}

# Main Script
Write-Host "============ Build process started ============" -ForegroundColor Green

Check-RequiredTools
Build-LlamaCpp

Write-Host "============ Build process complete ============" -ForegroundColor Green
