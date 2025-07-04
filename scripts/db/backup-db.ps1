param(
    [string]$BackupName = "solo_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
)

Write-Host "Starting backup of Solo database..."
docker exec solo_postgres pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB -F c -f "/backups/$BackupName.dump"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backup completed successfully: ./backups/$BackupName.dump" -ForegroundColor Green
} else {
    Write-Host "Backup failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
