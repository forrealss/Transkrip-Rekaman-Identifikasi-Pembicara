"""Tahap 3: siapa bicara kapan. Cetak interval pembicara, lalu cocokkan dengan telinga.

Contoh:
  python latihan/03_diarize.py
  python latihan/03_diarize.py --jumlah 2
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transkrip import diarize  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--audio", default=str(ROOT / "work" / "uji.wav"))
ap.add_argument("--jumlah", type=int, default=None, help="jumlah pembicara kalau sudah diketahui")
a = ap.parse_args()

t = time.time()
pipeline = diarize.muat_pipeline()
interval = diarize.diarisasi(pipeline, a.audio, num_speakers=a.jumlah)
print(f"Selesai dalam {time.time() - t:.1f} detik\n")

for mulai, selesai, label in interval:
    print(f"{label} bicara dari detik {mulai:6.1f} sampai {selesai:6.1f}  ({selesai - mulai:4.1f}s)")

print("\nTotal waktu bicara:")
total = {}
for mulai, selesai, label in interval:
    total[label] = total.get(label, 0) + selesai - mulai
for label, dtk in sorted(total.items()):
    print(f"  {label}: {dtk:.1f} detik")
