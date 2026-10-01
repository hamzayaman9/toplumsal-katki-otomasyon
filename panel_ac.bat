@echo off
rem Toplumsal Katki Paneli: sunucuyu baslatir ve tarayicida acar. Kapatmak icin bu pencereyi kapat.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
rem Akilli Uygulama Denetimi .venv\Scripts\python.exe'yi engelleyebiliyor:
rem uv'nin temel Python'u + katki_calistir.py (venv paketlerini yukler) kullanilir.
set "BASEPY=%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
if exist "%BASEPY%" (
    set RUN="%BASEPY%" katki_calistir.py
) else (
    set UV=uv
    where uv >nul 2>nul || set UV=%LOCALAPPDATA%\hermes\bin\uv.exe
    set RUN="%UV%" run python -m katki
)
start "" http://localhost:8000
%RUN% web --port 8000
pause
