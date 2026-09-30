@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NTM System
set PYTHONIOENCODING=utf-8

rem --- Find a Python that actually runs.
rem --- "where python" is not enough: Windows 10/11 ships a fake
rem --- python.exe stub that only opens the Microsoft Store, so each
rem --- candidate is executed once to prove it really works.
rem --- Flat gotos only: parenthesised blocks have parser pitfalls.
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
echo Starting with: %PYEXE%
%PYEXE% -V
echo.
%PYEXE% server.py %*
if errorlevel 1 goto FAILED
goto END

:NOPYTHON
type help_no_python.txt
goto END

:FAILED
echo.
type help_failed.txt
goto END

:END
echo.
pause
