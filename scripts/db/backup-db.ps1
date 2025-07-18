"""
Module Name: backup-db.ps1
Purpose   : Creates a backup of the Solo PostgreSQL database
Params    :
    - BackupName: Custom name for the backup file
    - Format: Backup format (c=custom, p=plain, d=directory)
    - Compress: Whether to compress the backup
    - RetainDays: Number of days to keep backups
History   :
    Date          Notes
    07.05.2025    Initial implementation
"""

param(
    [string]$BackupName = "solo_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')",
    [ValidateSet('c', 'p', 'd', 't')]
    [string]$Format = 'c',
    [switch]$Compress = $true,
    [int]$RetainDays = 30,
    [switch]$IncludeSchema = $true,
    [switch]$IncludeData = $true,
    [string]$SchemaOnly = ""
)

# Create formatted arguments
$formatArgs = "-F $Format"
$compressArgs = if ($Compress) { "-Z 9" } else { "" }
$dataArgs = if ($IncludeData -and -not $IncludeSchema) { "--data-only" }
            elseif ($IncludeSchema -and -not $IncludeData) { "--schema-only" }
            else { "" }
$schemaFilter = if ($SchemaOnly) { "-n $SchemaOnly" } else { "" }

Write-Host "Starting backup of Solo database..." -ForegroundColor Cyan
$startTime = Get-Date

# Execute the backup
docker exec solo_postgres pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB $formatArgs $compressArgs $dataArgs $schemaFilter -f "/backups/$BackupName.dump"

if ($LASTEXITCODE -eq 0) {
    $endTime = Get-Date
    $duration = ($endTime - $startTime).TotalSeconds
    Write-Host "Backup completed successfully in $duration seconds: ./backups/$BackupName.dump" -ForegroundColor Green

    # Cleanup old backups if retention period is specified
    if ($RetainDays -gt 0) {
        $cutoffDate = (Get-Date).AddDays(-$RetainDays)
        Write-Host "Cleaning up backups older than $RetainDays days..." -ForegroundColor Yellow

        docker exec solo_postgres find /backups -name "*.dump" -type f -mtime +$RetainDays -delete
        Write-Host "Cleanup completed." -ForegroundColor Yellow
    }
} else {
    Write-Host "Backup failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
