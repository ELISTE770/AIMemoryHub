@echo off
chcp 65001 > nul
title קימפול קובץ התקנה v1.0.1 עם Inno Setup
echo ========================================================
echo   🔨 קימפול קובץ התקנה v1.0.1 Enterprise עם Inno Setup Compiler (ISCC)
echo ========================================================
echo.

set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not exist "%ISCC_PATH%" (
    echo לא נמצא ISCC.exe בנתיב ברירת המחדל, מחפש במערכת...
    where ISCC.exe >nul 2>nul
    if %errorlevel% equ 0 (
        set "ISCC_PATH=ISCC.exe"
    ) else (
        echo ❌ Inno Setup לא נמצא! נא לוודא שהוא מותקן.
        pause
        exit /b 1
    )
)

echo מריץ את Inno Setup Compiler על installer.iss...
"%ISCC_PATH%" installer.iss

if exist "dist_installer\AIMemoryHub_Setup.exe" (
    echo מעתיק את קובץ ההתקנה לתיקייה הראשית...
    copy /y "dist_installer\AIMemoryHub_Setup.exe" "AIMemoryHub_Setup.exe" > nul
    echo.
    echo ========================================================
    echo   ✅ הקימפול הושלם בהצלחה!
    echo   הקובץ נוצר ב: AIMemoryHub_Setup.exe
    echo ========================================================
) else (
    echo.
    echo ❌ אירעה שגיאה בעת הקימפול של Inno Setup.
)

if "%~1"=="" pause
