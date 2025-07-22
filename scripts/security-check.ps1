<#
.SYNOPSIS
Run security checks on the Solo project codebase

.DESCRIPTION
This script runs bandit security checks on the codebase and generates a report.

.PARAMETER OutputFormat
The output format for the security report: 'txt', 'json', 'xml', or 'html'. Default is 'txt'.

.PARAMETER Severity
The minimum severity level to report: 'low', 'medium', or 'high'. Default is 'medium'.

.PARAMETER FailOnMedium
Whether to fail the build if medium or higher severity issues are found. Default is true.

.EXAMPLE
.\scripts\security-check.ps1                    # Run with default settings
.\scripts\security-check.ps1 -OutputFormat html # Generate HTML report
.\scripts\security-check.ps1 -Severity low      # Report all issues including low severity

.NOTES
Requires bandit to be installed. Run setup-test-env.ps1 first to install dependencies.
#>

param (
    [ValidateSet('txt', 'json', 'xml', 'html')]
    [string]$OutputFormat = 'txt',

    [ValidateSet('low', 'medium', 'high')]
    [string]$Severity = 'medium',

    [bool]$FailOnMedium = $true
)

Write-Host "================= Running Security Checks =================" -ForegroundColor Green

try {
    # Check if bandit is installed
    Write-Host "[Security] Checking bandit installation..."
    $banditInstalled = poetry run pip list | Select-String "bandit"

    if (-not $banditInstalled) {
        Write-Warning "[Security] Bandit not found, installing..."
        poetry add bandit --group dev

        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install bandit"
        }
    }

    # Set output file
    $outputFile = "security-report.$OutputFormat"
    Write-Host "[Security] Will generate report in $OutputFormat format: $outputFile"

    # Set severity flag
    $severityFlag = "-ll"
    if ($Severity -eq "low") {
        $severityFlag = "-l"
    } elseif ($Severity -eq "high") {
        $severityFlag = "-lll"
    }

    # Run bandit
    Write-Host "[Security] Running bandit security check with $Severity severity level..."
    poetry run bandit -r app $severityFlag -f $OutputFormat -o $outputFile
    $banditExitCode = $LASTEXITCODE

    # Report results
    if ($banditExitCode -eq 0) {
        Write-Host "[Security] No security issues found." -ForegroundColor Green
    } elseif ($banditExitCode -eq 1) {
        Write-Warning "[Security] Security issues found! See $outputFile for details."

        # Show a summary if text format
        if ($OutputFormat -eq 'txt') {
            Get-Content $outputFile | Select-Object -Last 10
        }

        # Fail the build if configured
        if ($FailOnMedium) {
            throw "Security check failed: medium or high severity issues found"
        }
    } else {
        throw "Bandit execution failed with exit code $banditExitCode"
    }
} catch {
    Write-Error "[Security] An error occurred during security check at line $($_.InvocationInfo.ScriptLineNumber):`n$_"
    exit 1
}

Write-Host "================= Security Check Complete =================" -ForegroundColor Green
