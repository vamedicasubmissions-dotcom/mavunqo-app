@echo off
title Push Mavunqo to GitHub & Render
cd /d "D:\Mavunqo"

echo ========================================================
echo Pushing Mavunqo Platform Updates to GitHub:
echo https://github.com/vamedicasubmissions-dotcom/mavunqo-app.git
echo ========================================================
echo.

where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    for /d %%i in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do (
        if exist "%%i\resources\app\git\cmd\git.exe" (
            set "PATH=%%i\resources\app\git\cmd;%PATH%"
            goto :found_git
        )
    )
    for /d %%i in ("%LOCALAPPDATA%\Programs\Git\cmd") do (
        if exist "%%i\git.exe" (
            set "PATH=%%i;%PATH%"
            goto :found_git
        )
    )
    if exist "C:\Program Files\Git\cmd\git.exe" (
        set "PATH=C:\Program Files\Git\cmd;%PATH%"
        goto :found_git
    )
    echo.
    echo Opening GitHub Desktop to push commits...
    start "" "%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe"
    pause
    exit /b 1
)

:found_git
git status
echo.
echo Staging updated platform files...
git add backend\ frontend\
echo.
git commit -m "Add clothing boutique, direct photo upload, catalog pricing, and single-language registration to Mavunqo"
echo.
echo Pushing to GitHub (origin main)...
git push origin main

echo.
echo ========================================================
echo Done! GitHub and Render have been updated.
echo ========================================================
pause
