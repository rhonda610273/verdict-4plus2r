@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NTM Account
set PYTHONIOENCODING=utf-8

rem --- Creates a login account without having to type any paths.
rem --- Keep this file pure ASCII: Chinese inside a .bat desyncs cmd's
rem --- byte-offset parser under chcp 65001. Chinese lives in the .txt files.

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
type help_account.txt
echo.
set ACCOUNT=
set /p ACCOUNT=Account: 
if "%ACCOUNT%"=="" goto CANCEL

echo.
type help_role.txt
echo.
set PICK=
set /p PICK=Choose 1 / 2 / 3: 

set ROLE=
if "%PICK%"=="1" set ROLE=viewer
if "%PICK%"=="2" set ROLE=editor
if "%PICK%"=="3" set ROLE=admin
if "%ROLE%"=="" goto CANCEL

echo.
type help_password.txt
echo.
%PYEXE% tools\manage_user.py add "%ACCOUNT%" --role %ROLE%
goto LIST

:CANCEL
echo.
type help_cancelled.txt
goto END

:NOPYTHON
type help_no_python.txt
goto END

:LIST
echo.
echo ----- current accounts -----
%PYEXE% tools\manage_user.py list

:END
echo.
pause
