@echo off
echo Starting Document Extractor Frontend...
echo.
echo The frontend will open in your browser at http://localhost:8080
echo.
echo Make sure the backend is running on http://localhost:8000
echo.

REM Try to use Python's built-in server
python --version >nul 2>&1
if %errorlevel% == 0 (
    start http://localhost:8080
    python -m http.server 8080
    exit /b
)

REM Fallback to Node.js if available
node --version >nul 2>&1
if %errorlevel% == 0 (
    start http://localhost:8080
    npx serve -p 8080
    exit /b
)

echo ERROR: Neither Python nor Node.js found.
echo Please install Python from https://python.org
echo Or install Node.js from https://nodejs.org
pause