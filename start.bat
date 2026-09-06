@echo off
chcp 65001 > nul
title Universal AI Memory Hub
echo =======================================================
echo   🧠 Universal AI Memory Hub - מרכז זיכרון למודלים
echo =======================================================
echo.
echo מפעיל את השרת המקומי...
start http://localhost:3456
python web_server.py
pause
