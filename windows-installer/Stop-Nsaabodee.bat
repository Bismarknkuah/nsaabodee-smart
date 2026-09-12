@echo off
REM Stops Nsaabodee Smart. Your data is safe - this does NOT delete
REM anything, it just stops the running containers. Run Start-Nsaabodee.bat
REM (or Install-Nsaabodee.bat) to bring it back up again.
cd /d "%~dp0.."
docker compose down
echo.
echo Nsaabodee Smart has been stopped. Your data has not been deleted.
echo.
pause
