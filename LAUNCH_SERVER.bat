@echo off
echo ========================================
echo   NFT Scout - Starting Web Server
echo ========================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!


    echo Please run start.ps1 first to set up the environment.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting web server on http://localhost:8080
echo Open http://localhost:8080 in your browser
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python web_server.py

pause

