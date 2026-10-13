"""Tahap 1: ubah rekaman jadi WAV 16 kHz mono, lalu ambil potongan uji.

Contoh:
  python latihan/01_siapkan_audio.py "assets/rekaman.m4a"
  python latihan/01_siapkan_audio.py "assets/rekaman.m4a" --mulai 300 --durasi 90 --bersihkan
Hasil: work/uji.wav (dipakai latihan 02-04)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transkrip import audio  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("rekaman")
ap.add_argument("--mulai", type=float, default=0, help="detik awal potongan")
ap.add_argument("--durasi", type=float, default=120, help="panjang potongan (detik)")
ap.add_argument("--bersihkan", action="store_true", help="pakai filter pembersih noise + normalisasi volume")
ap.add_argument("--keluar", default=str(ROOT / "work" / "uji.wav"))
a = ap.parse_args()

print(f"Durasi asli : {audio.durasi_detik(a.rekaman):.1f} detik")
hasil = audio.ke_wav(a.rekaman, a.keluar, bersihkan=a.bersihkan, mulai=a.mulai, durasi=a.durasi)
print(f"Potongan    : {hasil} ({audio.durasi_detik(hasil):.1f} detik, 16 kHz mono)")
