@echo off
echo Starting GPMS Decho.
echo Starting Streamlit server...
echo Dashboard will open in your browser automatically
echo Close this window to stop the dashboard
echo.
streamlit run maintenance_dashboard.py --server.port 8501echo.
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
echo Starting Streamlit server...
echo Server will start in a moment...
start /b streamlit run maintenance_dashboard.py --server.port 8501 --server.headless true
timeout /t 3 /nobreak >nul
echo Opening browser...
start "" "http://localhost:8501"
echo.
echo Dashboard is now running at http://localhost:8501
echo To stop the dashboard, close this window
echo.

pause
