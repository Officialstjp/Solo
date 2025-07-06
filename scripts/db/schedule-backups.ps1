<#
Module Name: schedule-backups.ps1
Purpose   : Sets up scheduled backups of Solo PostgreSQL database
Params    :
    - TimeOfDay: The time to run the backup (HH:mm format)
    - DaysOfWeek: Which days to run the backup
    - RetainDays: Number of days to keep backups
History   :
    Date          Notes
    07.05.2025    Initial implementation
#>

param(
    [string]$TimeOfDay = "03:00",
    [string[]]$DaysOfWeek = @("Monday", "Wednesday", "Friday"),
    [int]$RetainDays = 30,
    [switch]$UninstallTask = $false
)

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupScript = Join-Path $scriptPath "backup-db.ps1"
$taskName = "SoloDatabaseBackup"
$taskDescription = "Scheduled backup of Solo PostgreSQL database"

# Get the current user for task creation
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($UninstallTask) {
    Write-Host "Uninstalling scheduled backup task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Scheduled backup task removed." -ForegroundColor Green
    exit 0
}

# Create the scheduled task action
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$backupScript`" -RetainDays $RetainDays"

# Create the scheduled task trigger
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At $TimeOfDay

# Task settings
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -RunOnlyIfNetworkAvailable

# Register the scheduled task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description $taskDescription -User $currentUser -RunLevel Highest -Force

Write-Host "Scheduled backup task created successfully." -ForegroundColor Green
Write-Host "Task will run at $TimeOfDay on $($DaysOfWeek -join ', ')" -ForegroundColor Cyan
Write-Host "Backups will be retained for $RetainDays days" -ForegroundColor Cyan
Write-Host "To remove the scheduled task, run this script with -UninstallTask" -ForegroundColor Yellow
