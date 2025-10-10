@echo off
title GPMS Dashboard
color 0B

echo ========================================
echo  GPMS Maintenance Dashboard
echo ========================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Quick check for Python
set PYTHON_CMD=
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo Python not found in PATH. Please run INSTALL_AND_RUN.bat first.
        pause
        exit /b 1
    )
)

REM Quick check for Streamlit
%PYTHON_CMD% -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo Required packages not installed. Please run INSTALL_AND_RUN.bat first.
    pause
    exit /b 1
)

REM Check for required files
if not exist "maintenance_dashboard.py" (
    echo ✗ maintenance_dashboard.py not found!
    echo Make sure you're running this from the correct folder.
    pause
    exit /b 1
)

if not exist "Asset Work History.xlsx" (
    echo ✗ Asset Work History.xlsx not found!
    echo Make sure the Excel file is in this folder.
    pause
    exit /b 1
)

echo Starting GPMS Maintenance Dashboard...
echo Dashboard will open in your browser in a few seconds.
echo.
echo Close this window to stop the dashboard.
echo.

REM Start the dashboard
%PYTHON_CMD% -m streamlit run maintenance_dashboard.py --server.port 8501 --browser.gatherUsageStats false

echo.
echo Dashboard closed.
pause
