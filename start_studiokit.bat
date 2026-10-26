@echo off
setlocal
cd /d "%~dp0"

echo === StudioKit (FL Studio companion) ===
echo.

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv venv || python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install -q -r requirements.txt

echo.
echo Launching StudioKit companion window...
python companion.py

echo.
echo StudioKit exited.
pause
