@echo off
REM Double-click this file to install and start Nsaabodee Smart.
REM Batch (.bat) files run directly when double-clicked in Windows
REM Explorer; PowerShell (.ps1) scripts don't, by design (Windows'
REM default execution policy blocks them) - this file exists purely to
REM be the thing you actually double-click, and hands off to the real
REM logic in install.ps1 with the one-time bypass flag PowerShell
REM itself documents for exactly this situation.
REM
REM Uses the FULL, fixed install path to powershell.exe rather than
REM relying on it being found via PATH - some machines have had that
REM folder missing from PATH (from other software, IT policy, or a
REM corrupted user PATH variable), which broke the bare "powershell"
REM command entirely. %SystemRoot% is a core Windows variable set by
REM the OS itself at boot and the WindowsPowerShell subfolder location
REM has been fixed since Windows 7, so this works regardless of PATH.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
