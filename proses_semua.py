"""Proses semua rekaman di folder assets/ -> output/<nama>.txt + .json

Contoh:
  python proses_semua.py
  python proses_semua.py --model large-v3-turbo --jumlah 2 --bersihkan
  python proses_semua.py --ulang      # proses ulang walau output sudah ada
"""
import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from transkrip.asr import UKURAN_MODEL  # noqa: E402
from transkrip.audio import EKSTENSI_AUDIO  # noqa: E402
from transkrip.pipeline import FOLDER_OUTPUT, proses  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--folder", default=str(ROOT / "assets"))
ap.add_argument("--model", default="large-v3", choices=UKURAN_MODEL)
ap.add_argument("--jumlah", type=int, default=None, help="jumlah pembicara (kosongkan = otomatis)")
ap.add_argument("--bersihkan", action="store_true")
ap.add_argument("--prompt", action="store_true", help="beri petunjuk kosakata Etira ke Whisper")
ap.add_argument("--ulang", action="store_true")
a = ap.parse_args()

files = sorted(p for p in Path(a.folder).rglob("*") if p.suffix.lower() in EKSTENSI_AUDIO)
if not files:
    sys.exit(f"Tidak ada rekaman di {a.folder}")

gagal = []
for i, f in enumerate(files, 1):
    if not a.ulang and (FOLDER_OUTPUT / f"{f.stem}.txt").exists():
        print(f"({i}/{len(files)}) lewati {f.name} (output sudah ada)")
        continue
    print(f"\n({i}/{len(files)}) {f.name}")
    try:
        proses(f, ukuran_model=a.model, num_speakers=a.jumlah, bersihkan=a.bersihkan, pakai_prompt=a.prompt)
    except Exception:
        traceback.print_exc()
        gagal.append(f.name)

print(f"\nSelesai. {len(files) - len(gagal)} berhasil, {len(gagal)} gagal{': ' + ', '.join(gagal) if gagal else ''}")

import laporan_kualitas  # noqa: E402

laporan_kualitas.main()
