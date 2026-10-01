"""katki'yi .venv\\Scripts\\python.exe olmadan çalıştırır.

Windows Akıllı Uygulama Denetimi venv başlatıcısını (python.exe) engelleyebiliyor.
Bu betik uv'nin temel Python'u ile çalıştırılır, venv paketlerini yol'a ekler:
    <uv python> katki_calistir.py web --port 8000
"""
import runpy
import site
import sys
from pathlib import Path

kok = Path(__file__).resolve().parent
site.addsitedir(str(kok / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(kok))
runpy.run_module("katki", run_name="__main__", alter_sys=True)
