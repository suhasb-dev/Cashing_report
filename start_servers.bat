@echo off
REM Cache Failure Classification System - Server Startup Script for Windows
REM This script starts both the Flask API server and React development server

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo 🚀 Starting Cache Failure Classification System UI
echo ============================================================

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "UI_DIR=%PROJECT_ROOT%ui"

REM Check if we're in the right directory
if not exist "%PROJECT_ROOT%api_server.py" (
    echo ❌ api_server.py not found. Please run this script from the project root directory.
    pause
    exit /b 1
)

REM Check if UI directory exists
if not exist "%UI_DIR%" (
    echo ❌ UI directory not found. Please run the setup first.
    pause
    exit /b 1
)

REM Check if node_modules exists
if not exist "%UI_DIR%\node_modules" (
    echo ⚠️  Node modules not found. Installing dependencies...
    cd /d "%UI_DIR%"
    call npm install
    if errorlevel 1 (
        echo ❌ Failed to install node modules
        pause
        exit /b 1
    )
    echo ✅ Node modules installed successfully
    cd /d "%PROJECT_ROOT%"
)

REM Check if virtual environment is activated
if "%VIRTUAL_ENV%"=="" (
    echo ⚠️  Virtual environment not detected. Make sure to activate it first.
    echo ℹ️  Run: report\Scripts\activate
)

REM Check if API dependencies are installed
echo ℹ️  Checking API dependencies...
python -c "import flask, flask_cors" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  API dependencies not found. Installing...
    pip install -r api_requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install API dependencies
        pause
        exit /b 1
    )
    echo ✅ API dependencies installed successfully
)

REM Start API server
echo 🚀 Starting Flask API server...
cd /d "%PROJECT_ROOT%"
start "API Server" cmd /k "python api_server.py"

REM Wait a moment for API server to start
timeout /t 3 /nobreak >nul

REM Start React app
echo ⚛️  Starting React development server...
cd /d "%UI_DIR%"
set "BROWSER=none"
start "React App" cmd /k "npm start"

REM Wait a moment for React app to start
timeout /t 5 /nobreak >nul

REM Success message
echo.
echo ============================================================
echo ✅ Both servers are starting up!
echo ============================================================
echo 📡 API Server: http://localhost:5000
echo ⚛️  React App: http://localhost:3000
echo ============================================================
echo ℹ️  Press any key to close this window
echo ============================================================
echo.

pause
