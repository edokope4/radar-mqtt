@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
call .venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
call .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name RadarMqtt main.py
if errorlevel 1 goto fail
echo.
echo Ejecutable listo: dist\RadarMqtt.exe
echo.
pause
exit /b 0

:fail
echo.
echo No se pudo generar dist\RadarMqtt.exe
echo.
pause
exit /b 1
