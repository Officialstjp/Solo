<#
.SYNOPSIS
Apply database migrations for test environment

.DESCRIPTION
This script applies migrations to the test database using alembic.

.PARAMETER ConnectionString
The database connection string for the test database.

.EXAMPLE
.\scripts\setup\apply-db-migrations.ps1 "postgresql://postgres:postgres@localhost:5433/test_solo"

.NOTES
Requires the alembic configuration to be properly set up.
#>

param (
    [Parameter(Mandatory=$true)]
    [string]$ConnectionString
)

Write-Host "================= Applying Database Migrations =================" -ForegroundColor Green

try {
    # Check if alembic is installed
    Write-Host "[Migrations] Checking alembic installation..."
    $alembicInstalled = poetry run pip list | Select-String "alembic"

    if (-not $alembicInstalled) {
        Write-Warning "[Migrations] Alembic not found, installing..."
        poetry add alembic --group dev
    }

    # Set the connection string environment variable
    Write-Host "[Migrations] Setting database connection string..."
    $env:TEST_DATABASE_URL = $ConnectionString

    # Apply migrations
    Write-Host "[Migrations] Applying database migrations..."
    poetry run alembic upgrade head

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[Migrations] Database migrations applied successfully." -ForegroundColor Green
    } else {
        throw "Failed to apply database migrations"
    }
} catch {
    Write-Error "[Migrations] An error occurred while applying migrations at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    exit 1
}

Write-Host "================= Database Migrations Complete =================" -ForegroundColor Green
