@echo off
rem Haftalik calistirma: yedek al -> tum kaynaklari tara -> yenileri siniflandir -> sayisal rapor yaz -> AU baglantilari -> buluta gonder.
rem Panel (panel_ac.bat) aciksa ilerleme http://localhost:8000/canli adresinden canli izlenebilir.
rem Yaklasik 1 saat surer; bilgisayar prize takili ve kapagi acik kalsin.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
rem Akilli Uygulama Denetimi .venv\Scripts\python.exe'yi engelleyebiliyor:
rem uv'nin temel Python'u + katki_calistir.py (venv paketlerini yukler) kullanilir.
set "BASEPY=%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
if exist "%BASEPY%" (
    set PY="%BASEPY%" katki_calistir.py
) else (
    set UV=uv
    where uv >nul 2>nul || set UV=%LOCALAPPDATA%\hermes\bin\uv.exe
    set PY="%UV%" run python -m katki
)
echo [1/5] Tarama ve siniflandirma (once veritabani yedegi alinir)...
%PY% run --limit 20
echo [2/5] Yarida kalan siniflandirmalar (varsa)...
%PY% classify --limit 50000
echo [3/5] Sayisal rapor...
%PY% rapor
echo [4/5] Ankara Universitesi baglantilari (yerel benzerlik modeli)...
%PY% baglanti-kur
echo [5/5] Yeni kayitlar Vercel paneline (bulut veritabani) gonderiliyor...
%PY% bulut-esitle
echo.
echo Bitti. Rapor dosyalari: raporlar\  (haftalik karsilastirma: raporlar\haftalik_ozet.csv)
pause
