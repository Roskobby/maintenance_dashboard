    @echo off
echo Starting GPMS Dashboard...
echo.
cd /d "%~dp0"
echo Working directory: %CD%
echo.

if exist "maintenance_dashboard.py" (
    echo ✓ Dashboard file found
) else (
    echo ✗ Dashboard file NOT found
    pause
    exit /b 1
)

if exist "Asset Work History.xlsx" (
    echo ✓ Excel file found
) else (
    echo ✗ Excel file NOT found
)

echo.
echo Checking if dashboard is already running...
netstat -an | find "8501" >nul
if %errorlevel%==0 (
    echo Dashboard is already running! Opening browser...
    start "" "http://localhost:8501"
    pause
    exit /b 0
)

echo.
echo Checking system requirements...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.11 or later from python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
) else (
    echo ✓ Python found
)

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ ERROR: Streamlit is not installed
    echo.
    echo Installing Streamlit and required packages...
    python -m pip install streamlit pandas plotly openpyxl
    if %errorlevel% neq 0 (
        echo ✗ Failed to install required packages
        echo Please run: python -m pip install streamlit pandas plotly openpyxl
        pause
        exit /b 1
    )
) else (
    echo ✓ Streamlit found
)

echo.
echo Starting Streamlit server...
echo Dashboard will open in your browser automatically
echo Close this window to stop the dashboard
echo.
streamlit run maintenance_dashboard.py --server.port 8501
