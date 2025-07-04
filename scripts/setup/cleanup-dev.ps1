# Clean up script for Solo project
Write-Host "================= Environment Cleanup =================" -ForegroundColor Cyan

# 1. Remove llama.cpp directory if it exists
if (Test-Path "llama.cpp") {
    Write-Host "Removing llama.cpp directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force llama.cpp
    Write-Host "llama.cpp directory removed." -ForegroundColor Green
} else {
    Write-Host "llama.cpp directory not found, skipping." -ForegroundColor Gray
}

# 2. Clear environment variables
Write-Host "Clearing environment variables..."
Remove-Item env:CMAKE_ARGS -ErrorAction SilentlyContinue
Remove-Item env:FORCE_CMAKE -ErrorAction SilentlyContinue
Write-Host "Environment variables cleared." -ForegroundColor Green

# 3. Remove Poetry environments
Write-Host "Removing Poetry environments..."
poetry env remove --all
Write-Host "Poetry environments removed." -ForegroundColor Green

# 4. Clear Poetry cache
Write-Host "Clearing Poetry cache..."
poetry cache clear --all pypi
Write-Host "Poetry cache cleared." -ForegroundColor Green

# 5. Check for Python packages that might interfere
Write-Host "Checking for global llama-cpp-python installation..."
$globalInstall = pip list | Select-String "llama-cpp-python"
if ($globalInstall) {
    Write-Host "Found global installation of llama-cpp-python. This might interfere with Poetry." -ForegroundColor Red
    Write-Host "Consider removing it with: pip uninstall llama-cpp-python" -ForegroundColor Red
} else {
    Write-Host "No global llama-cpp-python installation found." -ForegroundColor Green
}

Write-Host "================= Cleanup Complete =================" -ForegroundColor Green
Write-Host "You can now run .\scripts\setup-dev.ps1 to set up a fresh environment."
