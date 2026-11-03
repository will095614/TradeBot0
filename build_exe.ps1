# TradeBot0 Native Windows GPU Executable Builder
$ErrorActionPreference = "Stop"

# Ensure Anaconda shared C-extension DLLs (ffi.dll, libssl, libcrypto, sqlite3, liblzma, libbz2) are in PATH
if (Test-Path "C:\ProgramData\anaconda3\Library\bin") {
    $env:PATH = "C:\ProgramData\anaconda3\Library\bin;" + $env:PATH
}

# Stop any running instances to release file locks on dist folder
Get-Process -Name "TradeBot0_Arena*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

Write-Host "[*] Packaging TradeBot0_Arena.exe via PyInstaller..." -ForegroundColor Cyan
.\.venv\Scripts\pyinstaller.exe --noconfirm --onedir --windowed --name "TradeBot0_Arena" `
    --collect-all webview `
    --collect-all clr_loader `
    --collect-all pythonnet `
    --hidden-import clr `
    --exclude-module dearpygui `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

Write-Host "[*] Verifying packaged executable with --self-test..." -ForegroundColor Cyan
$proc = Start-Process -FilePath "dist\TradeBot0_Arena\TradeBot0_Arena.exe" -ArgumentList "--self-test" -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    throw "Self-test failed with exit code $($proc.ExitCode)"
}
Write-Host "[+] TradeBot0_Arena.exe built and verified successfully!" -ForegroundColor Green

