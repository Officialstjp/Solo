# Test Auth Endpoints
# Purpose: Test registration and login without authentication

param (
    [switch]$Verbose
)

$apiBaseUrl = "http://localhost:8080"
$username = "testuser"
$password = "SecureTestPassword123!"
$email = "test@example.com"

# Create colorful output functions
function Write-Header {
    param([string]$text)
    Write-Host "`n$text" -ForegroundColor Cyan
    Write-Host ("-" * $text.Length) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$text)
    Write-Host "$text" -ForegroundColor Green
}

function Write-Error {
    param([string]$text)
    Write-Host "$text" -ForegroundColor Red
}

function Write-Info {
    param([string]$text)
    Write-Host "ℹ$text" -ForegroundColor Yellow
}

Write-Header "Testing Auth Endpoints"

# Test basic connectivity
try {
    $response = Invoke-WebRequest -Uri "$apiBaseUrl/status" -Method GET -TimeoutSec 5
    Write-Success "Server is running: $($response.StatusCode)"
    if ($Verbose) {
        $content = $response.Content | ConvertFrom-Json
        Write-Info "Server status: $($content | ConvertTo-Json -Depth 3)"
    }
}
catch {
    Write-Error "Server not running or not responding"
    Write-Info "Error: $($_.Exception.Message)"
    exit
}

# Test registration
Write-Header "Testing User Registration"
$registerBody = @{
    username = $username
    email = $email
    password = $password
    full_name = "Test User"
} | ConvertTo-Json

try {
    $regResponse = Invoke-RestMethod -Uri "$apiBaseUrl/auth/register" -Method POST -Body $registerBody -ContentType 'application/json'
    Write-Success "Registration successful for user: $($regResponse.username)"
    if ($Verbose) {
        Write-Info "User details: $($regResponse | ConvertTo-Json)"
    }
}
catch {
    Write-Error "Registration failed"
    Write-Info "Status code: $($_.Exception.Response.StatusCode.value__)"
    Write-Info "Response: $($_.ErrorDetails.Message)"
}

# Test login
Write-Header "Testing User Login"
$loginBody = @{
    username = $username
    password = $password
    remember = $true
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod -Uri "$apiBaseUrl/auth/login" -Method POST -Body $loginBody -ContentType 'application/json'
    Write-Success "Login successful"
    Write-Info "Token: $($loginResponse.access_token.Substring(0, 20))..."
    Write-Info "Expires in: $($loginResponse.expires_in) seconds"

    # Store token for further testing
    $token = $loginResponse.access_token
    $headers = @{ "Authorization" = "Bearer $token" }

    # Test an authenticated endpoint
    Write-Header "Testing Authenticated Endpoint"
    try {
        $models = Invoke-RestMethod -Uri "$apiBaseUrl/models/list" -Method GET -Headers $headers
        Write-Success "Authenticated request successful"
        Write-Info "Found $($models.Count) models"
        if ($Verbose -and $models.Count -gt 0) {
            Write-Info "First model: $($models[0] | ConvertTo-Json)"
        }
    }
    catch {
        Write-Error "Authenticated request failed"
        Write-Info "Status code: $($_.Exception.Response.StatusCode.value__)"
        Write-Info "Response: $($_.ErrorDetails.Message)"
    }
}
catch {
    Write-Error "Login failed"
    Write-Info "Status code: $($_.Exception.Response.StatusCode.value__)"
    Write-Info "Response: $($_.ErrorDetails.Message)"
}

Write-Header "Test Complete"
