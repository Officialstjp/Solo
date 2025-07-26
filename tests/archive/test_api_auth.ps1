# Solo API Testing Script with Authentication
# Purpose: Test the Solo API endpoints with proper authentication
# Usage: .\test_api_auth.ps1

# Configuration
$apiBaseUrl = "http://localhost:8080"
$username = "testuser"
$password = "SecureTestPassword123!"
$email = "test@example.com"

# Output formatting
function Write-Header {
    param([string]$text)
    Write-Host "`n$text" -ForegroundColor Cyan
    Write-Host ("-" * $text.Length) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$text)
    Write-Host "✅ $text" -ForegroundColor Green
}

function Write-Error {
    param([string]$text)
    Write-Host "❌ $text" -ForegroundColor Red
}

function Write-Info {
    param([string]$text)
    Write-Host "ℹ️ $text" -ForegroundColor Yellow
}

# Check if API is running
Write-Header "Checking API Availability"
try {
    # This will fail with 401, but that's OK - it means the API is running
    Invoke-RestMethod -Uri "$apiBaseUrl/models/list" -Method GET -ErrorAction SilentlyContinue
    Write-Error "API responded with success without authentication - check your auth middleware"
}
catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 401) {
        Write-Success "API is running and authentication middleware is active"
    }
    else {
        Write-Error "API is not responding. Make sure the server is running."
        Write-Info "Error: $($_.Exception.Message)"
        exit
    }
}

# Register a new user
Write-Header "Step 1: User Registration"
try {
    $registerBody = @{
        username = $username
        email = $email
        password = $password
        full_name = "Test User"
    } | ConvertTo-Json

    $userResult = Invoke-RestMethod -Uri "$apiBaseUrl/auth/register" -Method POST -Body $registerBody -ContentType 'application/json' -ErrorAction SilentlyContinue
    Write-Success "User registered successfully: $($userResult.username)"
}
catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 400 -and
        $_.ErrorDetails.Message -match "already exists") {
        Write-Info "User already exists, continuing to login"
    }
    else {
        Write-Info "Registration failed: $($_.Exception.Message)"
        Write-Info "Response: $($_.ErrorDetails.Message)"
        Write-Info "Continuing to login anyway..."
    }
}

# Login to get token
Write-Header "Step 2: User Authentication"
try {
    $loginBody = @{
        username = $username
        password = $password
        remember = $true
    } | ConvertTo-Json

    $loginResponse = Invoke-RestMethod -Uri "$apiBaseUrl/auth/login" -Method POST -Body $loginBody -ContentType 'application/json'
    $token = $loginResponse.access_token

    Write-Success "Login successful!"
    Write-Info "Token: $($token.Substring(0, 20))... (expires in $($loginResponse.expires_in) seconds)"

    # Set up headers for subsequent requests
    $headers = @{
        "Authorization" = "Bearer $token"
    }
}
catch {
    Write-Error "Login failed. Cannot continue testing without authentication."
    Write-Info "Error: $($_.Exception.Message)"
    Write-Info "Response: $($_.ErrorDetails.Message)"
    exit
}

# Test models endpoint
Write-Header "Step 3: Testing Models Endpoint"
try {
    $models = Invoke-RestMethod -Uri "$apiBaseUrl/models/list" -Method GET -Headers $headers
    Write-Success "Retrieved $(($models | Measure-Object).Count) models:"

    foreach ($model in $models) {
        Write-Info "  - $($model.name) ($($model.parameter_size), $($model.quantization))"
    }
}
catch {
    Write-Error "Failed to get models list"
    Write-Info "Error: $($_.Exception.Message)"
    Write-Info "Response: $($_.ErrorDetails.Message)"
}

# Test LLM generation
Write-Header "Step 4: Testing LLM Generation"
try {
    $prompt = "Tell me a joke about programming in one sentence."

    $generateBody = @{
        prompt = $prompt
        max_tokens = 100
        temperature = 0.7
    } | ConvertTo-Json

    Write-Info "Sending prompt: $prompt"
    $generationResult = Invoke-RestMethod -Uri "$apiBaseUrl/llm/generate" -Method POST -Body $generateBody -Headers $headers -ContentType 'application/json'

    Write-Success "Text generation successful!"
    Write-Host "`nResponse: $($generationResult.response)" -ForegroundColor White
    Write-Info "Tokens: $($generationResult.tokens_generated), Time: $($generationResult.generation_time_ms)ms"
    Write-Info "Speed: $($generationResult.tokens_per_second) tokens/sec"
}
catch {
    Write-Error "Text generation failed"
    Write-Info "Error: $($_.Exception.Message)"
    Write-Info "Response: $($_.ErrorDetails.Message)"
}

# Test user profile endpoints
Write-Header "Step 5: Testing User Profile Endpoints"
try {
    $userProfile = Invoke-RestMethod -Uri "$apiBaseUrl/users/me" -Method GET -Headers $headers
    Write-Success "Retrieved user profile for $($userProfile.username)"
    Write-Info "User ID: $($userProfile.user_id)"
    Write-Info "Email: $($userProfile.email)"

    # Test preference retrieval
    $preferences = Invoke-RestMethod -Uri "$apiBaseUrl/users/preferences" -Method GET -Headers $headers
    Write-Success "Retrieved user preferences"
    Write-Info "Theme: $($preferences.theme)"
    Write-Info "Language: $($preferences.language)"

    # Test profile update
    $updateBody = @{
        full_name = "Updated Test User"
        preferences = @{
            theme = "light"
            language = "fr"
        }
    } | ConvertTo-Json

    $updatedProfile = Invoke-RestMethod -Uri "$apiBaseUrl/users/me" -Method PUT -Headers $headers -Body $updateBody -ContentType 'application/json'
    Write-Success "Updated user profile"
    Write-Info "New name: $($updatedProfile.full_name)"
}
catch {
    Write-Error "User profile operations failed"
    Write-Info "Error: $($_.Exception.Message)"
    Write-Info "Response: $($_.ErrorDetails.Message)"
}

Write-Header "API Testing Complete"
