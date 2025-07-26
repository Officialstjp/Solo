# Solo API and Database Testing Script
# Purpose: Run API and database tests for the Solo application
# Usage: .\test_solo.ps1 [--api] [--db] [--all]

param (
    [switch]$Api,
    [switch]$Db,
    [switch]$All
)

# If no specific test is requested, default to all
if (-not $Api -and -not $Db) {
    $All = $true
}

# Set environment variables (if needed)
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if (-not [string]::IsNullOrWhiteSpace($_) -and -not $_.StartsWith("#")) {
            $key, $value = $_ -split '=', 2
            [Environment]::SetEnvironmentVariable($key, $value)
        }
    }
}

Write-Host "Solo Testing Utility" -ForegroundColor Cyan
Write-Host "===================" -ForegroundColor Cyan

# Run API tests
if ($Api -or $All) {
    Write-Host "`nRunning API Tests..." -ForegroundColor Green

    # Check if API is running
    $testConnection = $false
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080/" -Method GET -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $testConnection = $true
        }
    }
    catch {
        Write-Host "API server doesn't appear to be running. Start the server first." -ForegroundColor Red
        Write-Host "Run 'python -m app.main' to start the server." -ForegroundColor Yellow
        $testConnection = $false
    }

    if ($testConnection) {
        # Run API tests
        poetry run python ".\test_endpoints.py" --test all
    }
}

# Run Database tests
if ($Db -or $All) {
    Write-Host "`nRunning Database Tests..." -ForegroundColor Green
    poetry run python ".\test_db.py" --test all
}

Write-Host "`nTesting complete!" -ForegroundColor Cyan
