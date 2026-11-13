@echo off
title Mavunqo Web Server
cd /d D:\Mavunqo
echo Starting Mavunqo Local Server on http://localhost:8080 ...
.\.venv\Scripts\python.exe -m backend.server
pause
