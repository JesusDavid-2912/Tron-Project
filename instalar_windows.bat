@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 goto :missing_python
    set "PYTHON_CMD=python"
) else (
    set "PYTHON_CMD=py -3"
)

%PYTHON_CMD% -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
if errorlevel 1 goto :old_python

%PYTHON_CMD% -c "import tkinter" >nul 2>nul
if errorlevel 1 goto :missing_tk

if not exist ".build-venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .build-venv
    if errorlevel 1 goto :build_failed
)

set "BUILD_PYTHON=%CD%\.build-venv\Scripts\python.exe"
"%BUILD_PYTHON%" -m pip install --upgrade pip pyinstaller
if errorlevel 1 goto :build_failed

if not exist "build\windows\specs" mkdir "build\windows\specs"
if not exist "dist\windows" mkdir "dist\windows"

"%BUILD_PYTHON%" -m PyInstaller --clean --noconfirm --onefile --windowed --name TronCliente --distpath "dist\windows" --workpath "build\windows\client" --specpath "build\windows\specs" client.py
if errorlevel 1 goto :build_failed

"%BUILD_PYTHON%" -m PyInstaller --clean --noconfirm --onefile --name TronServidor --distpath "dist\windows" --workpath "build\windows\server" --specpath "build\windows\specs" server.py
if errorlevel 1 goto :build_failed

echo.
echo Aplicaciones creadas en dist\windows:
echo   TronCliente.exe
echo   TronServidor.exe
echo Copia ambos ejecutables al equipo que corresponda. El servidor debe permitir TCP 5050.
pause
exit /b 0

:missing_python
echo No se encontro Python. Instala Python 3.10 o posterior y vuelve a intentarlo.
goto :build_failed

:old_python
echo Se requiere Python 3.10 o posterior.
goto :build_failed

:missing_tk
echo La instalacion de Python no incluye Tkinter. Reinstala Python incluyendo Tcl/Tk.
goto :build_failed

:build_failed
echo.
echo No se pudo completar la compilacion. Revisa el mensaje anterior y tu conexion a Internet.
pause
exit /b 1
