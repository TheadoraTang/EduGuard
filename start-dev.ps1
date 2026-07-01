$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv\Scripts\python.exe. Create the virtual environment first."
}

& $python (Join-Path $root "scripts\start_dev.py")
exit $LASTEXITCODE
