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
    echo ✗ ERROR: Required packages not installed
    echo.
    echo Installing all required packages...
    echo This may take a few minutes...
    echo.
    
    REM Try to install from requirements.txt if it exists
    if exist "requirements.txt" (
        echo Installing from requirements.txt...
        python -m pip install -r requirements.txt
    ) else (
        echo Installing core packages...
        python -m pip install streamlit pandas plotly openpyxl numpy pillow
    )
    
    if %errorlevel% neq 0 (
        echo ✗ Failed to install required packages
        echo.
        echo Please try running this manually:
        echo python -m pip install streamlit pandas plotly openpyxl numpy pillow
        echo.
        pause
        exit /b 1
    ) else (
        echo ✓ All packages installed successfully
    )
) else (
    echo ✓ Required packages found
)

echo.
echo Starting Streamlit server...
echo Dashboard will open in your browser automatically
echo Close this window to stop the dashboard
echo.
streamlit run maintenance_dashboard.py --server.port 8501
