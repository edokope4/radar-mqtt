@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 exit /b 1
call .venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1
call .venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed --name RadarMqtt main.py
if errorlevel 1 exit /b 1
echo.
echo Ejecutable listo: dist\RadarMqtt.exe
