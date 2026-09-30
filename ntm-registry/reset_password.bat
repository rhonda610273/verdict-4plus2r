@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NTM Reset Password
set PYTHONIOENCODING=utf-8

rem --- Resets the password of an existing account.
rem --- No old password is needed: anyone who can run this file already has
rem --- the database on disk, so asking for it would add no protection.
rem --- Keep this file pure ASCII (see add_user.bat for why).

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
echo.
echo ----- current accounts -----
%PYEXE% tools\manage_user.py list
echo.
type help_reset.txt
echo.
set ACCOUNT=
set /p ACCOUNT=Account: 
if "%ACCOUNT%"=="" goto CANCEL

echo.
type help_password.txt
echo.
%PYEXE% tools\manage_user.py passwd "%ACCOUNT%"
goto END

:CANCEL
echo.
type help_cancelled.txt
goto END

:NOPYTHON
type help_no_python.txt
goto END

:END
echo.
pause
