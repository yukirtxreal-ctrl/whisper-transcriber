@echo off
REM Launch the Whisper Transcriber dependency setup GUI.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" pyw -3 "%~dp0setup_whisper.py" %*
    exit /b 0
)

where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" pythonw "%~dp0setup_whisper.py" %*
    exit /b 0
)

echo.
echo  Python 3 is not installed -- it's needed to run the setup tool.
echo.
echo   1. Microsoft Store: search "Python 3.12"
echo   2. Installer:        https://www.python.org/downloads/
echo.
set /p OPEN="Open the Python download page now? (Y/N) "
if /I "%OPEN%"=="Y" start "" "https://www.python.org/downloads/"
echo.
echo  After installing Python, double-click this file again.
pause
endlocal
