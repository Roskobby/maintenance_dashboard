@echo off
title GPMS Dashboard - Installation and Setup
color 0A

echo ========================================
echo  GPMS Maintenance Dashboard Setup
echo ========================================
echo.

REM Change to the script directory
cd /d "%~dp0"

echo [STEP 1] Checking Python installation...
echo.

REM Try multiple ways to find Python
set PYTHON_CMD=
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :python_found
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :python_found
)

REM Check common installation paths
if exist "C:\Python311\python.exe" (
    set PYTHON_CMD=C:\Python311\python.exe
    goto :python_found
)

if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe
    goto :python_found
)

REM Python not found
echo ✗ PYTHON NOT FOUND!
echo.
echo SOLUTION:
echo 1. Download Python 3.11+ from https://python.org
echo 2. During installation, CHECK "Add Python to PATH"
echo 3. After installation, restart your computer
echo 4. Run this script again
echo.
echo If Python is already installed but not in PATH:
echo 1. Search for "Environment Variables" in Windows
echo 2. Add Python installation folder to PATH
echo 3. Restart Command Prompt and try again
echo.
goto :error_exit

:python_found
echo ✓ Python found: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

echo [STEP 2] Checking pip...
%PYTHON_CMD% -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ pip not working
    echo.
    echo Trying to install/repair pip...
    %PYTHON_CMD% -m ensurepip --upgrade
    if %errorlevel% neq 0 (
        echo ✗ Could not install pip
        goto :error_exit
    )
)
echo ✓ pip is working
echo.

echo [STEP 3] Upgrading pip...
%PYTHON_CMD% -m pip install --upgrade pip
echo.

echo [STEP 4] Installing required packages...
echo This will take 5-10 minutes. Please be patient.
echo.

REM Install each package individually with detailed output
echo Installing streamlit...
%PYTHON_CMD% -m pip install streamlit
if %errorlevel% neq 0 (
    echo ✗ Failed to install streamlit
    goto :manual_install
)
echo ✓ streamlit installed

echo Installing pandas...
%PYTHON_CMD% -m pip install pandas
if %errorlevel% neq 0 (
    echo ✗ Failed to install pandas
    goto :manual_install
)
echo ✓ pandas installed

echo Installing plotly...
%PYTHON_CMD% -m pip install plotly
if %errorlevel% neq 0 (
    echo ✗ Failed to install plotly
    goto :manual_install
)
echo ✓ plotly installed

echo Installing openpyxl...
%PYTHON_CMD% -m pip install openpyxl
if %errorlevel% neq 0 (
    echo ✗ Failed to install openpyxl
    goto :manual_install
)
echo ✓ openpyxl installed

echo Installing pillow...
%PYTHON_CMD% -m pip install pillow
if %errorlevel% neq 0 (
    echo ✗ Failed to install pillow
    goto :manual_install
)
echo ✓ pillow installed

echo.
echo ✓ All packages installed successfully!
echo.

echo [STEP 5] Checking required files...
if not exist "maintenance_dashboard.py" (
    echo ✗ maintenance_dashboard.py not found!
    goto :error_exit
)
echo ✓ Dashboard script found

if not exist "Asset Work History.xlsx" (
    echo ✗ Asset Work History.xlsx not found!
    echo Make sure the Excel file is in this folder.
    goto :error_exit
)
echo ✓ Data file found

echo.
echo [STEP 6] Starting dashboard...
echo Dashboard will open in your browser in a few seconds.
echo.
echo Starting server...

REM Start the dashboard
%PYTHON_CMD% -m streamlit run maintenance_dashboard.py --server.port 8501 --browser.gatherUsageStats false

goto :end

:manual_install
echo.
echo ========================================
echo  MANUAL INSTALLATION REQUIRED
echo ========================================
echo.
echo Some packages failed to install automatically.
echo Please run these commands manually:
echo.
echo 1. Open Command Prompt as Administrator
echo 2. Copy and paste each line below:
echo.
echo %PYTHON_CMD% -m pip install --upgrade pip
echo %PYTHON_CMD% -m pip install streamlit
echo %PYTHON_CMD% -m pip install pandas  
echo %PYTHON_CMD% -m pip install plotly
echo %PYTHON_CMD% -m pip install openpyxl
echo %PYTHON_CMD% -m pip install pillow
echo.
echo 3. After successful installation, run this script again
echo.
goto :error_exit

:error_exit
echo.
echo Press any key to exit...
pause >nul
exit /b 1

:end
echo Dashboard closed.
pause
