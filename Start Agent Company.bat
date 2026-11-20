@echo off
REM Windows: double-click this file to start Agent Company. It makes your first project folder,
REM sets everything up, and opens the World in your browser.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 agent_company.py launch %* & goto done)
where python >nul 2>nul && (python agent_company.py launch %* & goto done)
echo Python 3 isn't installed. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then double-click this file again.
:done
pause
