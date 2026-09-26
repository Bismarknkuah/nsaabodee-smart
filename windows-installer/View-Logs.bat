@echo off
REM Shows live logs from every running service - useful for figuring
REM out what went wrong if Install-Nsaabodee.bat or Start-Nsaabodee.bat
REM reported a problem. Press Ctrl+C to stop watching (this does not
REM stop Nsaabodee Smart itself).
cd /d "%~dp0.."
echo Showing live logs. Press Ctrl+C to stop watching (this will NOT stop the app).
echo.
docker compose logs -f --tail=200
pause
