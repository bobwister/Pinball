@echo off
cd /d "%~dp0"
python main.py %*
if errorlevel 1 (
    echo.
    echo Une erreur est survenue. Appuyez sur une touche pour fermer.
    pause >nul
)
