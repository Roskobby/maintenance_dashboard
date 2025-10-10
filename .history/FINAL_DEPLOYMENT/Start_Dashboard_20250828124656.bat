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

REM Check if Python is installed and in PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ ERROR: Python is not installed or not in PATH
    echo.
    echo SOLUTION:
    echo 1. Install Python 3.11+ from python.org
    echo 2. During installation, CHECK "Add Python to PATH"
    echo 3. If already installed, add Python to your PATH manually
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
) else (
    python --version
    echo ✓ Python found and accessible
)

REM Check if pip is working
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ ERROR: pip is not working
    echo.
    echo SOLUTION: Reinstall Python with "Add to PATH" checked
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
) else (
    echo ✓ pip is working
)

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ✗ Required packages not installed
    echo.
    echo Installing packages... This may take 5-10 minutes.
    echo Please wait and do not close this window.
    echo.
    
    REM Upgrade pip first
    echo Upgrading pip...
    python -m pip install --upgrade pip
    
    REM Install packages one by one with error handling
    echo.
    echo Installing core packages...
    python -m pip install streamlit
    if %errorlevel% neq 0 (
        echo ✗ Failed to install streamlit
        goto :install_error
    )
    
    python -m pip install pandas
    if %errorlevel% neq 0 (
        echo ✗ Failed to install pandas
        goto :install_error
    )
    
    python -m pip install plotly
    if %errorlevel% neq 0 (
        echo ✗ Failed to install plotly
        goto :install_error
    )
    
    python -m pip install openpyxl
    if %errorlevel% neq 0 (
        echo ✗ Failed to install openpyxl
        goto :install_error
    )
    
    python -m pip install pillow
    if %errorlevel% neq 0 (
        echo ✗ Failed to install pillow
        goto :install_error
    )
    
    echo.
    echo ✓ All packages installed successfully!
    echo.
) else (
    echo ✓ Required packages found
)

echo.
echo Starting Streamlit server...
echo Dashboard will open in your browser automatically
echo.

REM Check if the dashboard file exists
if not exist "maintenance_dashboard.py" (
    echo ✗ ERROR: maintenance_dashboard.py not found!
    echo Make sure you're running this from the correct folder.
    echo.
    goto :error_exit
)

if not exist "Asset Work History.xlsx" (
    echo ✗ ERROR: Asset Work History.xlsx not found!
    echo Make sure the Excel file is in the same folder.
    echo.
    goto :error_exit
)

echo Loading dashboard... This may take 30-60 seconds the first time.
echo.

REM Start streamlit and capture errors
streamlit run maintenance_dashboard.py --server.port 8501 2>error.log
if %errorlevel% neq 0 (
    echo.
    echo ✗ Dashboard failed to start!
    echo.
    if exist error.log (
        echo Error details:
        type error.log
    )
    echo.
    goto :error_exit
)

goto :end

:error_exit
echo.
echo Press any key to close...
pause >nul
exit /b 1

:install_error
echo.
echo ✗ Package installation failed!
echo.
echo MANUAL SOLUTION:
echo 1. Close this window
echo 2. Open Command Prompt as Administrator  
echo 3. Run these commands one by one:
echo.
echo    python -m pip install --upgrade pip
echo    python -m pip install streamlit
echo    python -m pip install pandas
echo    python -m pip install plotly
echo    python -m pip install openpyxl
echo    python -m pip install pillow
echo.
echo 4. Then try running this batch file again
echo.
echo Press any key to close...
pause >nul
exit /b 1

:end
