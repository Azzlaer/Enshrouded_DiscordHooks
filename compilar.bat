@echo off
title Compilador ESH - PyInstaller
echo ==========================================
echo  ENSHROUDED MONITOR - COMPILACION A EXE
echo ==========================================
echo.

REM -------- CONFIGURACION --------
set SCRIPT=monitor.py
set EXENAME=ESH
set ICON=logo.ico
set CONFIG=config.ini
set SQLITE=enshrouded.db

REM -------- VALIDACION --------
if not exist %SCRIPT% (
    echo ERROR: No se encuentra %SCRIPT%
    pause
    exit /b
)

if not exist %ICON% (
    echo ADVERTENCIA: No se encuentra el icono %ICON%
    echo El EXE se compilara sin icono.
)

echo Limpiando archivos previos de PyInstaller...
rmdir /s /q build >nul 2>&1
rmdir /s /q dist >nul 2>&1
del /q %EXENAME%.spec >nul 2>&1

echo.
echo ==========================================
echo Compilando...
echo ==========================================

pyinstaller ^
 --onefile ^
 --noconsole ^
 --name "%EXENAME%" ^
 --icon="%ICON%" ^
 --add-data "%CONFIG%;." ^
 --add-data "%ICON%;." ^
 --add-data "%SQLITE%;." ^
 --hidden-import=requests ^
 --hidden-import=sqlite3 ^
 --hidden-import=pathlib ^
 %SCRIPT%

echo.
echo ==========================================
echo  COMPILACION FINALIZADA
echo ==========================================
echo EXE generado en: dist\%EXENAME%.exe
echo.

pause
