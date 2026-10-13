@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py
if "%PY%"=="" where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo No encuentro Python. Instalalo desde https://www.python.org/downloads/
  echo y marca la casilla "Add Python to PATH" durante la instalacion.
  pause
  exit /b
)
echo Preparando (solo tarda la primera vez)...
%PY% -m pip install --quiet --disable-pip-version-check pillow imageio-ffmpeg
echo.
%PY% componer.py
echo.
pause
