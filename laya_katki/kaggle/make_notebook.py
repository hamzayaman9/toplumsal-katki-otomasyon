"""laya_finetune_katki_tr.ipynb'yi üretir; metrics.py, prep.py ve train_ddp.py notebook'a gömülür.

chatbot/laya_ft/kaggle/make_notebook.py'den uyarlandı (resmî Laya notebook'u, Apache-2.0).

    <python> -m laya_katki.kaggle.make_notebook
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
LAYA_VERSION = "0.3.20"
MODEL_NAME = "laya-katki-tr-v1"
NOTEBOOK = "laya_finetune_katki_tr.ipynb"


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}


def code(src: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": src.strip("\n").splitlines(keepends=True)}


def build() -> dict:
    metrics_src = (PKG / "metrics.py").read_text(encoding="utf-8")
    train_src = (HERE / "train_ddp.py").read_text(encoding="utf-8")
    prep_src = (HERE / "prep.py").read_text(encoding="utf-8")
    cells = [
        md(f"""
# Laya — Toplumsal Katkı Türkçe (`laya-multilingual` → `{MODEL_NAME}`)

Kurum haberlerinde karar soruları: `katki` (toplumsal katkı mı), `kategori`, `faaliyet`, `bolge` ve bölgeye
göre `il_*`. Etiketler Jev'den (typesafe/jev-1.13) damıtılmış yumuşak olasılıklar + koordinatörlük onayları.
Bölünme kaynak sitesine göre. Zero-shot ile fine-tuned modeli aynı `test`te karşılaştırır, `katki` eşiğini
calib'de seçer ve modelle birlikte kaydeder.

Resmî Laya notebook'undan uyarlanmıştır (`NandhaKishorM/laya`, Apache-2.0).

### Kaggle ayarları
* **Accelerator:** `GPU T4 x2` · **Internet:** `On` · **Input:** `laya-katki-tr` veri seti
"""),
        code("""
import os, torch
n_gpu = torch.cuda.device_count()
print(f"CUDA: {torch.cuda.is_available()} | GPUs: {n_gpu}")
for i in range(n_gpu):
    p = torch.cuda.get_device_properties(i)
    print(f"  GPU {i}: {p.name} ({p.total_memory / 1e9:.1f} GB)")
assert n_gpu >= 1, "GPU yok: Notebook options -> Accelerator -> GPU T4 x2 seç"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
"""),
        code(f"""
!pip install -q "laya=={LAYA_VERSION}" "transformers>=4.48.0" safetensors huggingface_hub
import laya, transformers
print("laya", laya.__version__, "| transformers", transformers.__version__, "| torch", torch.__version__)
"""),
        md("## 1. Ayarlar ve veri"),
        code(f"""
import glob, json, time
DATA_DIR = os.path.dirname(glob.glob("/kaggle/input/**/train.jsonl", recursive=True)[0])
WORK = "/kaggle/working"
MODEL_NAME = "{MODEL_NAME}"
OUTPUT_DIR = f"{{WORK}}/{{MODEL_NAME}}"
REPORT_DIR = f"{{WORK}}/reports"
os.makedirs(REPORT_DIR, exist_ok=True)

MODEL_ID = "convaiinnovations/laya-multilingual"
MAX_LEN = 768           # CPU çıkarım hızı için; bölge sorusunda bile ~240 token haber metni kalır
HEAD_MAX_LEN = 544      # bölge sorusu (10 seçenek, il listeleri) ~520 token
EPOCHS = 3
EVAL_SPLITS = ("test",)

def read_split(name):
    with open(f"{{DATA_DIR}}/{{name}}.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]

splits = {{s: read_split(s) for s in ("train", "calib") + EVAL_SPLITS}}
QUESTIONS = json.load(open(f"{{DATA_DIR}}/questions_tr.json", encoding="utf-8"))
print("DATA_DIR:", DATA_DIR, {{s: len(v) for s, v in splits.items()}}, "| sorular:", list(QUESTIONS))
"""),
        code("%%writefile /kaggle/working/metrics.py\n" + metrics_src),
        code("%%writefile /kaggle/working/prep.py\n" + prep_src),
        md("## 2. Ön işleme (resmî `build_sequence`)"),
        code("""
import sys
sys.path.insert(0, WORK)
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer
from laya.agent import _fix_tokenizer_config
from prep import build_items

model_dir = snapshot_download(MODEL_ID)
_fix_tokenizer_config(model_dir)
tok = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))

for name in ("train", "calib"):
    items, dropped = build_items(tok, splits[name], QUESTIONS, MAX_LEN, HEAD_MAX_LEN)
    torch.save(items, f"{WORK}/{name}_items.pt")
    print(f"{name}: {len(items)} items ({dropped} dropped for truncated options)")
"""),
        md("## 3. Zero-shot baseline (aynı test, GPU)"),
        code("""
from metrics import choose_thresholds, evaluate, summary_rows

def predict_rows(agent, rows, questions, batch=16):
    preds = []
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        res = agent.predict_batch([json.loads(r["state"]) for r in chunk], questions,
                                  max_len=MAX_LEN, head_max_len=HEAD_MAX_LEN)
        preds.extend(r["answers"] for r in res)
    return preds

def run_eval(agent, rows, questions, thresholds=None, save_as=None):
    t0 = time.time()
    preds = predict_rows(agent, rows, questions)
    m = evaluate(preds, [json.loads(r["gold"]) for r in rows], questions, thresholds)
    m["meta"] = {"n": len(rows), "seconds": round(time.time() - t0, 1)}
    if save_as:  # kayıt bazlı cevaplar: yerelde Jev ile karşılaştırma ve hata incelemesi için
        with open(f"{REPORT_DIR}/{save_as}", "w", encoding="utf-8") as f:
            for r, p in zip(rows, preds):
                f.write(json.dumps({"id": r["id"], "answers": p}, ensure_ascii=False) + "\\n")
    return m

def show(name, m):
    print(f"--- {name} ---")
    for q, line in summary_rows(m):
        print(f"{q:>22}: {line}")
    for k, v in m["acceptance"].items():
        val = "yok" if v["value"] is None else f"{v['value']:.3f}"
        print(f"  {'PASS' if v['pass'] else 'FAIL'} {k} = {val} (hedef {v['target']})")

base_agent = laya.load(MODEL_ID, device="cuda")
for split in EVAL_SPLITS:
    m = run_eval(base_agent, splits[split], QUESTIONS)
    m["meta"].update(model="zero-shot", split=split)
    json.dump(m, open(f"{REPORT_DIR}/zero_shot_{split}.json", "w"), indent=2, ensure_ascii=False)
    show(f"zero-shot [{split}]", m)
del base_agent
torch.cuda.empty_cache()
"""),
        md("## 4. Fine-tune (DDP, `torchrun`)"),
        code("%%writefile /kaggle/working/train_ddp.py\n" + train_src),
        code("""
cmd = (f"torchrun --standalone --nproc_per_node={n_gpu} {WORK}/train_ddp.py {model_dir} {OUTPUT_DIR} "
       f"{WORK}/train_items.pt {WORK}/calib_items.pt --epochs {EPOCHS} --max-len {MAX_LEN} "
       f"--head-max-len {HEAD_MAX_LEN} --model-name {MODEL_NAME}")
print(cmd)
t0 = time.time()
!{cmd}
print(f"Training wall time: {(time.time() - t0) / 60:.1f} min")
"""),
        md("## 5. Fine-tuned değerlendirme"),
        code("""
ft_agent = laya.load(OUTPUT_DIR, device="cuda")

# karar eşiği calib'de seçilir (test'te asla), modelle birlikte kaydedilir
calib_preds = predict_rows(ft_agent, splits["calib"], QUESTIONS)
THRESHOLDS = choose_thresholds(calib_preds, [json.loads(r["gold"]) for r in splits["calib"]], QUESTIONS)
print("calib'de seçilen eşikler:", THRESHOLDS)
cfg_path = f"{OUTPUT_DIR}/rl_agent_config.json"
cfg = json.load(open(cfg_path)); cfg["decision_thresholds"] = THRESHOLDS
json.dump(cfg, open(cfg_path, "w"), indent=2)

results = {}
for split in EVAL_SPLITS:
    m = run_eval(ft_agent, splits[split], QUESTIONS, THRESHOLDS, save_as=f"preds_{split}.jsonl")
    m["meta"].update(model=MODEL_NAME, split=split, thresholds=THRESHOLDS)
    json.dump(m, open(f"{REPORT_DIR}/finetuned_{split}.json", "w"), indent=2, ensure_ascii=False)
    show(f"fine-tuned [{split}]", m)
    results[split] = m

compare_rows = [("katki", "accuracy"), ("katki", "precision"), ("katki", "recall"), ("kategori", "accuracy"),
                ("faaliyet", "accuracy"), ("bolge", "accuracy"), ("il", "accuracy"), ("overall", "accuracy"),
                ("overall", "ece")]
for split in EVAL_SPLITS:
    zs, ft = json.load(open(f"{REPORT_DIR}/zero_shot_{split}.json")), results[split]
    print(f"\\n[{split}] metric                 zero-shot   fine-tuned")
    for q, k in compare_rows:
        z, f = zs.get(q, {}).get(k), ft.get(q, {}).get(k)
        print(f"{q + '.' + k:<30}{(z if z is not None else float('nan')):>10.3f}{(f if f is not None else float('nan')):>13.3f}")
"""),
        md("## 6. Paketle"),
        code("""
import shutil
shutil.rmtree(f"{OUTPUT_DIR}/checkpoint_latest", ignore_errors=True)
shutil.copytree(REPORT_DIR, f"{OUTPUT_DIR}/reports", dirs_exist_ok=True)
for tmp in ("train_items.pt", "calib_items.pt"):
    if os.path.exists(f"{WORK}/{tmp}"):
        os.remove(f"{WORK}/{tmp}")
print("Hazır:", OUTPUT_DIR)
"""),
    ]
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                                        "name": "python3"},
                                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


def main() -> None:
    out = HERE / NOTEBOOK
    out.write_text(json.dumps(build(), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
