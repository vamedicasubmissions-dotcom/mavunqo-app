@echo off
title Push Mavunqo to GitHub & Render
cd /d "D:\Mavunqo"

echo ========================================================
echo Pushing Mavunqo updates to GitHub:
echo https://github.com/vamedicasubmissions-dotcom/mavunqo-app.git
echo ========================================================
echo.

where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Git CLI was not found in your standard PATH.
    echo Trying to find GitHub Desktop's bundled Git...
    for /d %%i in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do (
        if exist "%%i\resources\app\git\cmd\git.exe" (
            set "PATH=%%i\resources\app\git\cmd;%PATH%"
            goto :found_git
        )
    )
    echo.
    echo Could not find git executable automatically.
    echo Opening GitHub Desktop for you...
    start "" "%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe"
    pause
    exit /b 1
)

:found_git
git status
echo.
echo Adding all updated files...
git add .
echo.
git commit -m "Implement Warm Caribbean Minimalist UI, Bilingual AI Concierge, and City Lights multi-vertical pilot"
echo.
echo Pushing to GitHub (origin main)...
git push origin main

echo.
echo ========================================================
echo Done! GitHub and Render have been updated.
echo ========================================================
pause
