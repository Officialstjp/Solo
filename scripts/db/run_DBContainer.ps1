try {
    Write-Host "Starting PostgreSQL container..."
    cmd.exe /c  "docker run --name PG_Solo -e POSTGRES_PASSWORD=J*bApp7ic4tion -d -p 5432:5432 pgvector/pgvector:pg17"
    #cmd.exe /c  "docker run --name SoloPostGres -e POSTGRES_PASSWORD=J*bApp7ic4tion -p 5431:5432 -d postgres"
    Write-Host "Container started successfully." -ForegroundColor Green
}
catch {
    Write-Host "Failed to start container: `n$_"
}
