@echo off
REM Double-click this to start Nsaabodee Smart on a normal day, after
REM Install-Nsaabodee.bat has already been run once.
REM Uses the full, fixed PowerShell install path rather than relying on
REM PATH - see Install-Nsaabodee.bat for why.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
