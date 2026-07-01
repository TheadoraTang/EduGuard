$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"
$pythonPath = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing .env. Copy .env.example to .env and configure PostgreSQL first."
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Missing .venv\Scripts\python.exe. Create the project virtual environment first."
}

$config = @{}
Get-Content -LiteralPath $envPath -Encoding UTF8 | ForEach-Object {
    if ($_ -match "^\s*([^#=\s]+)\s*=(.*)$") {
        $config[$matches[1]] = $matches[2].Trim()
    }
}

foreach ($key in @("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_PORT")) {
    if (-not $config.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($config[$key])) {
        throw "Missing $key in .env."
    }
}

$user = [System.Uri]::EscapeDataString($config["POSTGRES_USER"])
$password = [System.Uri]::EscapeDataString($config["POSTGRES_PASSWORD"])
$database = [System.Uri]::EscapeDataString($config["POSTGRES_DB"])
$port = $config["POSTGRES_PORT"]

$env:DATABASE_URL = "postgresql+psycopg://${user}:${password}@localhost:${port}/${database}"
Set-Location (Join-Path $root "backend")
& $pythonPath -m uvicorn app.main:app --reload

