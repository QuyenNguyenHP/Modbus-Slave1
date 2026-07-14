@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 goto :no_python
)
echo Installing/checking dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_error
".venv\Scripts\pythonw.exe" app.py
exit /b 0

:no_python
echo.
echo Python was not found. Install Python 3.10 or later from https://python.org
pause
exit /b 1

:install_error
echo.
echo Unable to install dependencies. Check your Internet connection and try again.
pause
exit /b 1
