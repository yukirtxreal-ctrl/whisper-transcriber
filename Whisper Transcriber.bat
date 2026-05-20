@echo off
REM Launch the Whisper Transcriber GUI. Tries the py launcher, then pythonw,
REM then falls through to a no-Python prompt.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" pyw -3 "%~dp0whisper_gui.py" %*
    exit /b 0
)

where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" pythonw "%~dp0whisper_gui.py" %*
    exit /b 0
)

echo.
echo  Python 3 is not installed -- this app needs it.
echo.
echo   1. Microsoft Store: search "Python 3.12"
echo   2. Installer:        https://www.python.org/downloads/
echo.
echo  Tip: run "Install Dependencies.bat" first to set everything up.
echo.
set /p OPEN="Open the Python download page now? (Y/N) "
if /I "%OPEN%"=="Y" start "" "https://www.python.org/downloads/"
pause
endlocal
