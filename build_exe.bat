@echo off
chcp 65001 > nul
title Building AIMemoryHub EXE
echo ========================================================
echo   Building Universal AI Memory Hub
echo ========================================================
echo.
python -m PyInstaller --noconsole --onefile --noconfirm --workpath "%TEMP%\pyi_work" --distpath "%TEMP%\pyi_dist" --icon "app_icon.ico" --add-data "app_icon.ico;." --add-data "app_icon.png;." --add-data "web;web" --collect-all customtkinter --collect-all pystray --collect-all keyboard --collect-all PIL --hidden-import requests --hidden-import urllib3 --hidden-import spotlight --hidden-import chat_miner --hidden-import gemini_optimizer --hidden-import memory_hub --hidden-import updater --hidden-import mcp_server --hidden-import web_server --name "AIMemoryHub" gui.py
echo.
if exist "%TEMP%\pyi_dist\AIMemoryHub.exe" (
    echo Copying executable...
    copy /y "%TEMP%\pyi_dist\AIMemoryHub.exe" "AIMemoryHub.exe" > nul
    if not exist "dist" mkdir "dist"
    copy /y "%TEMP%\pyi_dist\AIMemoryHub.exe" "dist\AIMemoryHub.exe" > nul
    echo.
    echo ========================================================
    echo   SUCCESS: Binary built at AIMemoryHub.exe
    echo ========================================================
) else (
    echo.
    echo Error: PyInstaller build failed.
)
if "%~1"=="" pause
