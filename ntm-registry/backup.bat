@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NTM Backup
set PYTHONIOENCODING=utf-8

rem --- Backs up data\ntm.db into backups\, keeping the newest 60 copies.
rem --- Double-click to back up now; the scheduled task calls it with /auto
rem --- so it will not wait for a key press.
set AUTO=0
if /i "%~1"=="/auto" set AUTO=1

rem --- Same Python probe as start.bat: execute each candidate, because
rem --- Windows ships a fake python.exe that only opens the Microsoft Store.
set PYEXE=

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set PYEXE=py -3
if defined PYEXE goto FOUND

python -c "import sys" >nul 2>&1
if not errorlevel 1 set PYEXE=python
if defined PYEXE goto FOUND

python3 -c "import sys" >nul 2>&1
if not errorlevel 1 set PYEXE=python3
if defined PYEXE goto FOUND

goto NOPYTHON

:FOUND
%PYEXE% tools\backup.py --keep 60
if errorlevel 1 goto FAILED
goto END

:NOPYTHON
type help_no_python.txt
goto END

:FAILED
echo.
echo BACKUP FAILED - see the message above.
goto END

:END
echo.
if "%AUTO%"=="1" goto QUIET
pause
:QUIET
