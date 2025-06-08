<#$
.SYNOPSIS
Run the Solo application using the Poetry environment.

.DESCRIPTION
Activates the Poetry virtual environment if available and launches the main program.
Shows a short usage message when called with -Help.

.PARAMETER Help
Displays usage information.

.NOTES
Module Name: run_agent.ps1
Purpose    : Start Solo via Poetry environment
Params     : [-Help]
History    : 2024-06-09 Assistant – Initial creation
#>

param(
    [switch]$Help
)

# ===== functions =====
# ---- helper functions ----
function Get-VenvPath {
    try {
        poetry env info -p 2>$null | ForEach-Object { $_.Trim() }
    } catch {
        Write-Error "Poetry environment not found. Run scripts/dev.ps1 first."
        exit 1
    }
}

function Show-Usage {
    Write-Host "Usage: .\\scripts\\run_agent.ps1 [-Help]" -ForegroundColor Yellow
    Write-Host "Ensures the Poetry virtual environment is active and runs app/main.py." -ForegroundColor Yellow
}

# ==== runtime ====
# ---- Init ----
if ($Help) {
    Show-Usage
    exit 0
}

$venvPath = Get-VenvPath
$activateScript = Join-Path $venvPath 'Scripts\Activate.ps1'

if (-not (Test-Path $activateScript)) {
    Write-Error "Activate script not found at $activateScript"
    exit 1
}

. $activateScript

# ---- main loop ----
$mainFile = 'app\main.py'
if (Test-Path $mainFile) {
    python $mainFile
} else {
    Write-Host "Main program not found. Use -Help for usage." -ForegroundColor Yellow
}
