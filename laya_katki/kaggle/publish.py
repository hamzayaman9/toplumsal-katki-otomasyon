"""Kaggle gidiş-dönüşü (resmî CLI, kimlik ~/.kaggle/kaggle.json). chatbot/laya_ft/kaggle/publish.py'den uyarlandı.

Kaggle CLI chatbot projesinin sanal ortamından çalışır (bu projenin venv'i Akıllı Uygulama Denetimi'ne takılıyor).

    <python> -m laya_katki.kaggle.publish dataset   # özel veri seti <kullanıcı>/laya-katki-tr (oluştur / yeni sürüm)
    <python> -m laya_katki.kaggle.publish kernel    # notebook'u gönder: özel, GPU T4 x2 + internet, hemen çalışır
    <python> -m laya_katki.kaggle.publish status    # çalışma durumu
    <python> -m laya_katki.kaggle.publish output    # modeli + raporları models/ altına indir
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
KAGGLE = os.environ.get("KAGGLE_EXE") or str(Path.home() / "Desktop" / "chatbot" / ".venv" / "Scripts" / "kaggle.exe")
DATASET_SLUG = "laya-katki-tr"
KERNEL_SLUG = "laya-katki-tr-finetune"
NOTEBOOK = "laya_finetune_katki_tr.ipynb"
UPLOAD_DIR = HERE.parent / "data" / "kaggle_upload"
PUSH_DIR = HERE / "push"
MODELS_DIR = ROOT / "models"


def username() -> str:
    with open(os.path.expanduser("~/.kaggle/kaggle.json"), encoding="utf-8") as f:
        return json.load(f)["username"]


def kaggle(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([KAGGLE, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(proc.stdout.strip() or proc.stderr.strip())
    if check and proc.returncode != 0:
        sys.exit(proc.returncode)
    return proc


def dataset() -> None:
    user = username()
    meta = {"title": DATASET_SLUG, "id": f"{user}/{DATASET_SLUG}", "licenses": [{"name": "other"}]}
    (UPLOAD_DIR / "dataset-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    exists = kaggle("datasets", "status", f"{user}/{DATASET_SLUG}", check=False).returncode == 0
    if exists:
        kaggle("datasets", "version", "-p", str(UPLOAD_DIR), "-m", "veri setini yeniden oluştur", "--dir-mode", "zip")
    else:
        kaggle("datasets", "create", "-p", str(UPLOAD_DIR), "--dir-mode", "zip")  # varsayılan özel


def kernel() -> None:
    user = username()
    PUSH_DIR.mkdir(exist_ok=True)
    shutil.copy(HERE / NOTEBOOK, PUSH_DIR / NOTEBOOK)
    meta = {
        "id": f"{user}/{KERNEL_SLUG}", "title": KERNEL_SLUG, "code_file": NOTEBOOK,
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": True, "enable_internet": True, "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [f"{user}/{DATASET_SLUG}"], "competition_sources": [], "kernel_sources": [],
    }
    (PUSH_DIR / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    kaggle("kernels", "push", "-p", str(PUSH_DIR))


def status() -> None:
    kaggle("kernels", "status", f"{username()}/{KERNEL_SLUG}")


def output() -> None:
    dest = MODELS_DIR / "kaggle_output"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    # dosya listesi sayfalanınca CLI sıfır dışı kodla çıkabiliyor; dosyaların hepsi yine iner
    kaggle("kernels", "output", f"{username()}/{KERNEL_SLUG}", "-p", str(dest), "--force", check=False)
    for model_dir in sorted(p for p in dest.iterdir() if p.is_dir() and p.name.startswith("laya-katki-tr-v")):
        target = MODELS_DIR / model_dir.name
        shutil.copytree(model_dir, target, dirs_exist_ok=True)
        print(f"model: {target}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["dataset", "kernel", "status", "output"])
    {"dataset": dataset, "kernel": kernel, "status": status, "output": output}[ap.parse_args().action]()


if __name__ == "__main__":
    main()
