# TradeBot0 Native Windows Standalone Executable Builder (Single Standalone .exe)
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        throw "Virtual environment Python not found at .venv\Scripts\python.exe. Create .venv and install requirements.txt first."
    }

    # Ensure Anaconda shared C-extension DLLs (ffi.dll, libssl, libcrypto, sqlite3, liblzma, libbz2) are in PATH
    if (Test-Path "C:\ProgramData\anaconda3\Library\bin") {
        $env:PATH = "C:\ProgramData\anaconda3\Library\bin;" + $env:PATH
    }

    # Stop any running instances to release file locks on dist folder
    Get-Process -Name "TradeBot0_Arena*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process | Where-Object { $_.Path -like "*TradeBot0_Arena*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    if (Test-Path "dist\TradeBot0_Arena.exe") {
        Remove-Item -Force "dist\TradeBot0_Arena.exe" -ErrorAction SilentlyContinue
    }

    Write-Host "[*] Packaging Single Standalone TradeBot0_Arena.exe via PyInstaller (--onefile)..." -ForegroundColor Cyan
    $pyiArgs = @(
        "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--windowed", "--name", "TradeBot0_Arena",
        "--add-data", "src/gui/assets;src/gui/assets"
    )
    if (Test-Path "src/gui/assets/splash_logo.png") {
        $pyiArgs += @("--splash", "src/gui/assets/splash_logo.png")
    } else {
        Write-Host "[!] Splash asset src/gui/assets/splash_logo.png not found; building without native splash." -ForegroundColor Yellow
    }
    if (Test-Path "src/compat/win7/api-ms-win-core-path-l1-1-0.dll") {
        $pyiArgs += @("--add-binary", "src/compat/win7/api-ms-win-core-path-l1-1-0.dll;.")
    } else {
        Write-Host "[!] Optional Win7 compat DLL not found; building without src/compat/win7/api-ms-win-core-path-l1-1-0.dll" -ForegroundColor Yellow
    }
    $pyiArgs += @(
        "--collect-all", "webview",
        "--collect-all", "clr_loader",
        "--collect-all", "pythonnet",
        "--collect-all", "websockets",
        "--hidden-import", "clr",
        "--exclude-module", "dearpygui",
        "main.py"
    )
    & .\.venv\Scripts\python.exe @pyiArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

    Write-Host "[*] Verifying packaged single standalone executable with --self-test..." -ForegroundColor Cyan
    $tmpAppData = Join-Path $env:TEMP ("tb0_selftest_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmpAppData -Force | Out-Null
    $prevAppData = $env:APPDATA
    $prevFastTest = $env:ARENA_FAST_TEST
    try {
        $env:APPDATA = $tmpAppData
        $env:ARENA_FAST_TEST = "1"
        $proc = Start-Process -FilePath "dist\TradeBot0_Arena.exe" -ArgumentList "--self-test" -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            throw "Self-test failed with exit code $($proc.ExitCode)"
        }
    } finally {
        $env:APPDATA = $prevAppData
        if ($null -eq $prevFastTest) {
            Remove-Item Env:ARENA_FAST_TEST -ErrorAction SilentlyContinue
        } else {
            $env:ARENA_FAST_TEST = $prevFastTest
        }
        Remove-Item -Recurse -Force $tmpAppData -ErrorAction SilentlyContinue
    }
    Write-Host "[+] Single Standalone TradeBot0_Arena.exe built and verified successfully!" -ForegroundColor Green
} finally {
    Pop-Location
}
