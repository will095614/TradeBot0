@echo off
setlocal EnableExtensions
pushd "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment Python not found: "%VENV_PY%"
    echo         Create it and install dependencies from requirements.txt first.
    popd
    exit /b 1
)

if /I "%~1"=="gui" goto :run_gui
if /I "%~1"=="self-test" goto :run_selftest
if /I "%~1"=="selftest" goto :run_selftest
if /I "%~1"=="cli" goto :run_cli
if /I "%~1"=="evolve" goto :run_evolve
if /I "%~1"=="pytest" goto :run_pytest
if /I "%~1"=="all" goto :run_all
if not "%~1"=="" (
    echo [ERROR] Unknown command: "%~1"
    echo         Valid commands: gui, self-test, cli, evolve, pytest, all
    popd
    exit /b 2
)

:menu
echo.
echo ============================================================
echo   TradeBot0 Dev Launcher
echo ============================================================
echo   [1] Launch Main App GUI        (.venv\...\python.exe main.py)
echo   [2] Self-Test                  (main.py --self-test)
echo   [3] CLI Backtest               (main.py --cli)
echo   [4] CLI Evolution Backtest     (main.py --cli --evolve 3)
echo   [5] Run Test Suite             (JS check + self-test + pytest)
echo   [6] Verify All, then Launch GUI
echo   [0] Exit
echo ============================================================
set "CHOICE="
set /p "CHOICE=Select an option [1-6, 0 to exit]: "
if defined CHOICE set "CHOICE=%CHOICE:"=%"

if "%CHOICE%"=="1" goto :run_gui
if "%CHOICE%"=="2" goto :run_selftest
if "%CHOICE%"=="3" goto :run_cli
if "%CHOICE%"=="4" goto :run_evolve
if "%CHOICE%"=="5" goto :run_pytest
if "%CHOICE%"=="6" goto :run_all
if "%CHOICE%"=="0" goto :done
echo Invalid selection: "%CHOICE%"
goto :menu

:run_gui
echo.
echo [TradeBot0] Starting GUI...
"%VENV_PY%" "%~dp0main.py"
set "RC=%ERRORLEVEL%"
goto :finish

:run_selftest
echo.
echo [TradeBot0] Running --self-test...
"%VENV_PY%" "%~dp0main.py" --self-test
set "RC=%ERRORLEVEL%"
goto :finish

:run_cli
echo.
echo [TradeBot0] Running --cli backtest...
"%VENV_PY%" "%~dp0main.py" --cli
set "RC=%ERRORLEVEL%"
goto :finish

:run_evolve
echo.
echo [TradeBot0] Running --cli --evolve 3...
"%VENV_PY%" "%~dp0main.py" --cli --evolve 3
set "RC=%ERRORLEVEL%"
goto :finish

:run_pytest
call :verify_suite
set "RC=%ERRORLEVEL%"
goto :finish

:run_all
call :verify_suite
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" goto :launch_gui_after_verify
echo.
echo [ERROR] Verification failed ^(exit code %RC%^).
if not "%~1"=="" goto :finish
set "LAUNCH_ANYWAY="
set /p "LAUNCH_ANYWAY=Launch GUI anyway? [y/N]: "
if defined LAUNCH_ANYWAY set "LAUNCH_ANYWAY=%LAUNCH_ANYWAY:"=%"
if /I not "%LAUNCH_ANYWAY%"=="y" goto :finish
:launch_gui_after_verify
echo.
if "%RC%"=="0" (
    echo [TradeBot0] All checks passed. Launching GUI...
) else (
    echo [TradeBot0] Continuing to GUI per user choice...
)
"%VENV_PY%" "%~dp0main.py"
set "RC=%ERRORLEVEL%"
goto :finish

:verify_suite
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo [1/3] Skipping node --check ^(node not on PATH^).
) else (
    echo.
    echo [1/3] Checking frontend JS syntax...
    node --check "%~dp0src\gui\assets\app.js"
    if errorlevel 1 exit /b 1
)
echo [2/3] Running main.py --self-test...
"%VENV_PY%" "%~dp0main.py" --self-test
if errorlevel 1 exit /b 1
echo [3/3] Running pytest suite ^(dev scope; skipping build-artifact checks^)...
set "PYTEST_TMP=%TEMP%\tb0_pytest_run_%RANDOM%_%RANDOM%"
if exist "%PYTEST_TMP%" rmdir /s /q "%PYTEST_TMP%" >nul 2>&1
"%VENV_PY%" -m pytest -q tests -k "not test_system_config_is_untracked_but_present_on_disk and not test_launchers_and_shortcut_integrity" --basetemp="%PYTEST_TMP%"
set "PYTEST_RC=%ERRORLEVEL%"
if exist "%PYTEST_TMP%" rmdir /s /q "%PYTEST_TMP%" >nul 2>&1
exit /b %PYTEST_RC%

:finish
echo.
if not "%RC%"=="0" echo [TradeBot0] Exited with code %RC%.
if "%~1"=="" (
    pause
    goto :menu
)
popd
exit /b %RC%

:done
popd
exit /b 0
