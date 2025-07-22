<#
.SYNOPSIS
Setup test environment for Solo project

.DESCRIPTION
This script sets up the test environment for the Solo project, including:
1. Creating a test database with docker-compose
2. Setting up test fixtures
3. Checking test dependencies

.PARAMETER Stop
Stops the test environment containers.

.PARAMETER RemoveData
When used with -Stop, also removes data volumes.

.EXAMPLE
.\scripts\setup\setup-test-env.ps1                        # Setup test environment
.\scripts\setup\setup-test-env.ps1 -Stop                  # Stop containers but keep data
.\scripts\setup\setup-test-env.ps1 -Stop -RemoveData      # Stop containers and remove data

.NOTES
Run this script before running tests for the first time.
#>

param (
    [switch]$Stop,
    [switch]$RemoveData
)

Write-Host "================= Test Environment Setup =================" -ForegroundColor Green

# --- 1. Check test dependencies ---
Write-Host "----------------- Checking Test Dependencies -----------------" -ForegroundColor Cyan
try {
    # Check if pytest and test dependencies are installed
    Write-Host "[Dependencies] Checking test dependencies..."

    $requiredPackages = @(
        "pytest",
        "pytest-cov",
        "pytest-asyncio",
        "pytest-benchmark",
        "pytest-httpserver",
        "testcontainers",
        "psutil",
        "locust",
        "bandit"
    )

    $missingPackages = @()
    foreach ($package in $requiredPackages) {
        $installed = poetry run pip list | Select-String $package
        if (-not $installed) {
            $missingPackages += $package
        }
    }

    if ($missingPackages.Count -gt 0) {
        Write-Warning "[Dependencies] Missing test dependencies: $($missingPackages -join ', ')"
        Write-Host "[Dependencies] Installing missing dependencies..."
        poetry add $missingPackages --group dev
    } else {
        Write-Host "[Dependencies] All test dependencies are installed." -ForegroundColor Green
    }

    # Verify pytest works
    Write-Host "[Dependencies] Verifying pytest installation..."
    poetry run pytest --version
    if ($LASTEXITCODE -ne 0) {
        throw "Pytest installation verification failed"
    }

    Write-Host "----------------- Test Dependencies Check Complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[Dependencies] An error occurred during dependency check at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    exit 1
}

# --- 2. Set up test database ---
Write-Host "`n----------------- Setting up Test Database -----------------" -ForegroundColor Cyan
try {
    # Check if Docker and Docker Compose are installed
    Write-Host "[Database] Checking Docker installation..."
    docker --version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not installed or not in PATH. Please install Docker and try again."
    }

    Write-Host "[Database] Checking Docker Compose installation..."
    docker compose version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose is not installed or not in PATH. Please install Docker Compose and try again."
    }

    # Check if the docker-compose file exists
    $composeFile = "docker-compose.test.yml"
    if (-not (Test-Path $composeFile)) {
        throw "Test docker-compose file not found at $composeFile"
    }

    # Check if containers are already running
    $containerName = "solo-test-db"
    $containerRunning = docker ps -q -f name=$containerName

    if (-not $containerRunning) {
        Write-Host "[Database] Starting test environment using docker-compose..."
        docker compose -f $composeFile up -d

        if ($LASTEXITCODE -ne 0) {
            throw "Failed to start test environment with docker-compose"
        }
    } else {
        Write-Host "[Database] Test database container is already running."
    }

    # Wait for the database to be ready
    Write-Host "[Database] Waiting for database to be ready..."
    $retries = 0
    $maxRetries = 10
    $ready = $false

    while (-not $ready -and $retries -lt $maxRetries) {
        $retries++

        try {
            # Use docker-compose exec to check readiness
            docker compose -f $composeFile exec -T test-db pg_isready -U postgres
            if ($LASTEXITCODE -eq 0) {
                $ready = $true
            } else {
                Write-Host "[Database] Database not ready yet, waiting 2 seconds... (Attempt $retries/$maxRetries)"
                Start-Sleep -Seconds 2
            }
        } catch {
            Write-Host "[Database] Error checking database readiness, waiting 2 seconds... (Attempt $retries/$maxRetries)"
            Start-Sleep -Seconds 2
        }
    }

    if (-not $ready) {
        throw "Database failed to become ready after $maxRetries attempts"
    }

    Write-Host "[Database] Test database is ready." -ForegroundColor Green

    # Apply database migrations
    Write-Host "[Database] Applying database migrations..."
    $dbConnectionString = "postgresql://postgres:postgres@localhost:5433/test_solo"
    & "$PSScriptRoot\apply-db-migrations.ps1" -ConnectionString $dbConnectionString

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[Database] Failed to apply database migrations. Tests may fail if schema is not up to date."
    }

    Write-Host "----------------- Test Database Setup Complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[Database] An error occurred during database setup at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    Write-Warning "[Database] You may need to set up the test database manually"
}

# --- 3. Add function to stop test environment ---
function Stop-TestEnvironment {
    param (
        [switch]$KeepData
    )

    Write-Host "`n----------------- Stopping Test Environment -----------------" -ForegroundColor Cyan

    $composeFile = "docker-compose.test.yml"
    if (Test-Path $composeFile) {
        if ($KeepData) {
            # Stop containers but keep volumes
            Write-Host "[Cleanup] Stopping test containers but keeping data..."
            docker compose -f $composeFile down
        } else {
            # Stop containers and remove volumes
            Write-Host "[Cleanup] Stopping test containers and removing data volumes..."
            docker compose -f $composeFile down -v
        }

        Write-Host "[Cleanup] Test environment stopped." -ForegroundColor Green
    } else {
        Write-Warning "[Cleanup] docker-compose.test.yml not found, cannot stop test environment"
    }

    Write-Host "----------------- Test Environment Stopped -----------------" -ForegroundColor Green
}

# --- 3. Set up test fixtures ---
Write-Host "`n----------------- Setting up Test Fixtures -----------------" -ForegroundColor Cyan
try {
    # Create the fixtures directory if it doesn't exist
    $fixturesDir = "tests/fixtures"
    if (-not (Test-Path $fixturesDir)) {
        Write-Host "[Fixtures] Creating fixtures directory..."
        New-Item -ItemType Directory -Path $fixturesDir -Force | Out-Null
    }

    # Create the models directory for model manager tests
    $modelsDir = "tests/fixtures/models"
    if (-not (Test-Path $modelsDir)) {
        Write-Host "[Fixtures] Creating test models directory..."
        New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null
    }

    # Check if we need to create a dummy model file for testing
    $dummyModelPath = "$modelsDir/test_model.gguf"
    if (-not (Test-Path $dummyModelPath)) {
        Write-Host "[Fixtures] Creating dummy model file for testing..."
        # Create a small binary file with the GGUF signature
        $bytes = [byte[]]@(0x47, 0x47, 0x55, 0x46) + (1..1020 | ForEach-Object { [byte]0 })
        [System.IO.File]::WriteAllBytes($dummyModelPath, $bytes)
    }

    Write-Host "----------------- Test Fixtures Setup Complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[Fixtures] An error occurred during fixtures setup at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
}

# --- 4. Set up .env.test file ---
Write-Host "`n----------------- Setting up Test Environment Variables -----------------" -ForegroundColor Cyan
try {
    $envTestPath = ".env.test"

    # Check if .env.test already exists
    if (-not (Test-Path $envTestPath)) {
        Write-Host "[Env] Creating .env.test file..."

        $envContent = @"
# Test environment variables
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/test_solo
TEST_MODELS_DIR=tests/fixtures/models
TEST_DEBUG=true
TEST_JWT_SECRET=test_secret_key_for_testing_only
TEST_JWT_EXPIRY=30m
# For docker-compose networking, use this DB URL when running tests in docker:
# TEST_DATABASE_URL=postgresql://postgres:postgres@test-db:5432/test_solo
"@

        $envContent | Out-File -FilePath $envTestPath -Encoding utf8
        Write-Host "[Env] .env.test file created." -ForegroundColor Green
    } else {
        Write-Host "[Env] .env.test file already exists." -ForegroundColor Green
    }

    Write-Host "----------------- Test Environment Variables Setup Complete -----------------" -ForegroundColor Green
} catch {
    Write-Error "[Env] An error occurred during environment variables setup at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
}

Write-Host "`n================= Test Environment Setup Complete =================" -ForegroundColor Green
Write-Host "`nYou can now run tests using the following commands:"
Write-Host "  poetry run python -m tests.run_tests           # Run all tests"
Write-Host "  poetry run python -m tests.run_tests --unit    # Run only unit tests"
Write-Host "  poetry run python -m tests.run_tests --coverage --html  # Run tests with coverage and HTML report"
Write-Host "`nTo stop the test environment:"
Write-Host "  .\scripts\setup\setup-test-env.ps1 -Stop              # Stop containers but keep data"
Write-Host "  .\scripts\setup\setup-test-env.ps1 -Stop -RemoveData  # Stop containers and remove all data"

# Handle command line parameters
if ($Stop) {
    Stop-TestEnvironment -KeepData:(-not $RemoveData)
    exit 0
}
