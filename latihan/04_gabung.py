"""Tahap 4: gabungkan teks + pembicara, simpan ke output/uji.txt.

Contoh:
  python latihan/04_gabung.py
  python latihan/04_gabung.py --model large-v3-turbo --jumlah 2
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transkrip import asr, diarize, gabung  # noqa: E402
from transkrip.gpu import bebaskan_vram  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--audio", default=str(ROOT / "work" / "uji.wav"))
ap.add_argument("--model", default="large-v3", choices=asr.UKURAN_MODEL)
ap.add_argument("--jumlah", type=int, default=None)
a = ap.parse_args()

model = asr.muat_model(a.model)
segmen, _ = asr.transkripsi(model, a.audio)
del model
bebaskan_vram()

pipeline = diarize.muat_pipeline()
interval = diarize.diarisasi(pipeline, a.audio, num_speakers=a.jumlah)

baris = gabung.gabungkan(segmen, interval)
print(gabung.ke_teks(baris))
path_txt, _ = gabung.simpan(baris, ROOT / "output", Path(a.audio).stem, {"Model": a.model}, segmen, interval)
print(f"Tersimpan: {path_txt}")
