# TradeBot0 Native Windows Standalone Executable Builder (Single Standalone .exe)
$ErrorActionPreference = "Stop"

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
$proc = Start-Process -FilePath "dist\TradeBot0_Arena.exe" -ArgumentList "--self-test" -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    throw "Self-test failed with exit code $($proc.ExitCode)"
}
Write-Host "[+] Single Standalone TradeBot0_Arena.exe built and verified successfully!" -ForegroundColor Green
