"""Tahap 2: suara -> teks. Cetak tiap segmen sebagai [mulai - selesai] teks.

Contoh:
  python latihan/02_asr.py                         # model large-v3 pada work/uji.wav
  python latihan/02_asr.py --model small large-v3  # bandingkan dua ukuran model
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transkrip import asr  # noqa: E402
from transkrip.gpu import bebaskan_vram  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--audio", default=str(ROOT / "work" / "uji.wav"))
ap.add_argument("--model", nargs="+", default=["large-v3"], choices=asr.UKURAN_MODEL)
a = ap.parse_args()

ringkasan = []
for ukuran in a.model:
    print(f"\n=== Model {ukuran} ===")
    t = time.time()
    model = asr.muat_model(ukuran)
    t_muat = time.time() - t
    t = time.time()
    segmen, info = asr.transkripsi(model, a.audio)
    t_proses = time.time() - t
    for s in segmen:
        print(f"[{s['mulai']:7.2f} - {s['selesai']:7.2f}] {s['teks']}   (logprob {s['avg_logprob']:.2f})")
    ringkasan.append((ukuran, t_muat, t_proses, info.duration, len(segmen)))
    del model
    bebaskan_vram()

print("\nPerbandingan:")
for ukuran, t_muat, t_proses, durasi, n in ringkasan:
    print(f"  {ukuran:15s} muat {t_muat:5.1f}s  proses {t_proses:6.1f}s  ({durasi / t_proses:4.1f}x real-time)  {n} segmen")
