@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NTM Backup Schedule

rem --- Registers a daily Windows scheduled task that runs backup.bat.
rem --- Runs as the current user, so administrator rights are not needed.
rem --- Task name: NTM_Backup    Default time: 18:00
rem --- Change the time:  setup_backup.bat 12:30

set TASKNAME=NTM_Backup
set TASKTIME=%1
if "%TASKTIME%"=="" set TASKTIME=18:00

echo.
echo   Task     : %TASKNAME%
echo   Runs     : every day at %TASKTIME%
echo   Folder   : %~dp0
echo.

schtasks /create /tn "%TASKNAME%" /tr "\"%~dp0backup.bat\" /auto" /sc daily /st %TASKTIME% /f
if errorlevel 1 goto FAILED

echo.
schtasks /query /tn "%TASKNAME%" /fo list | findstr /i "TaskName Next"
echo.
type help_backup_ok.txt
goto END

:FAILED
echo.
type help_backup_failed.txt
goto END

:END
echo.
pause
