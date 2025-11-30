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
echo Starting Streamlit server...
start "" "http://localhost:8501"
streamlit run maintenance_dashboard.py --server.port 8501

pause
