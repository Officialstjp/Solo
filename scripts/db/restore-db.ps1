"""
Module Name: restore-db.ps1
Purpose   : Restores the Solo PostgreSQL database from a backup
Params    :
    - BackupFile: Name of the backup file to restore
    - Clean: Whether to drop objects before restoring
    - CreateDB: Create the database before restoring
    - NoOwner: Don't include ownership commands in restore
History   :
    Date          Notes
    07.05.2025    Enhanced implementation
"""

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [switch]$Clean = $true,
    [switch]$CreateDB = $false,
    [switch]$NoOwner = $false
)

if (-not (Test-Path "./backups/$BackupFile")) {
    Write-Host "Backup file not found: ./backups/$BackupFile" -ForegroundColor Red
    exit 1
}

# Build pg_restore options
$cleanOption = if ($Clean) { "-c" } else { "" }
$createDBOption = if ($CreateDB) { "-C" } else { "" }
$noOwnerOption = if ($NoOwner) { "-O" } else { "" }

Write-Host "Restoring Solo database from backup: $BackupFile" -ForegroundColor Cyan
$startTime = Get-Date

docker exec -i solo_postgres pg_restore -U $env:POSTGRES_USER -d $env:POSTGRES_DB $cleanOption $createDBOption $noOwnerOption -F c "/backups/$BackupFile"

$exitCode = $LASTEXITCODE
$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

if ($exitCode -eq 0) {
    Write-Host "Restore completed successfully in $duration seconds" -ForegroundColor Green
} else {
    Write-Host "Restore completed with warnings/errors in $duration seconds (exit code: $exitCode)" -ForegroundColor Yellow
    Write-Host "Note: Some errors are expected if objects don't exist when using -c option" -ForegroundColor Yellow
}
