param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)

if (-not (Test-Path "./backups/$BackupFile")) {
    Write-Host "Backup file not found: ./backups/$BackupFile" -ForegroundColor Red
    exit 1
}

Write-Host "Restoring Solo database from backup..."
docker exec -i solo_postgres pg_restore -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c -F c "/backups/$BackupFile"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Restore completed successfully" -ForegroundColor Green
} else {
    Write-Host "Restore failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
