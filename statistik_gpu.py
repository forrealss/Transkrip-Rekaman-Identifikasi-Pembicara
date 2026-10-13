"""Rata-rata pemakaian GPU selama proses, dipisah per tahap.

Cara pakai:
  1. Sebelum/selama proses, catat GPU tiap detik (jendela PowerShell terpisah):
       powershell -ExecutionPolicy Bypass -File catat_gpu.ps1
  2. Jalankan proses dengan log:  python -u proses_semua.py > work\\log_proses.txt
  3. Setelah selesai:  python statistik_gpu.py

Tahap ditentukan dari baris log proses_semua.py:
  "transkripsi dengan ..." -> Speech-to-text (Whisper)
  "diarization pyannote"   -> Pengenal pembicara (pyannote)
  "selesai ->"             -> tahap berakhir
"""
import argparse
import re
import statistics
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("--gpu", default=str(ROOT / "work" / "gpu_log.csv"))
ap.add_argument("--log", default=str(ROOT / "work" / "log_proses.txt"))
a = ap.parse_args()

# --- baca log GPU -------------------------------------------------------------
sampel = []  # (waktu, util %, memori MiB, total MiB, daya W, suhu C)
for baris in Path(a.gpu).read_text(encoding="utf-8-sig", errors="replace").splitlines():
    kolom = [k.strip() for k in baris.split(",")]
    if len(kolom) < 6:
        continue
    try:
        t = datetime.strptime(kolom[0].split(".")[0], "%Y/%m/%d %H:%M:%S")
        util, mem, total = float(kolom[1]), float(kolom[2]), float(kolom[3])
        daya = float(kolom[4]) if kolom[4] not in ("[N/A]", "N/A") else None
        suhu = float(kolom[5])
    except ValueError:
        continue
    sampel.append((t, util, mem, total, daya, suhu))
if not sampel:
    raise SystemExit(f"Tidak ada data di {a.gpu}")
tanggal = sampel[0][0].date()

# --- baca log proses -> rentang waktu tiap tahap -------------------------------
rentang = {"Speech-to-text (Whisper)": [], "Pengenal pembicara (pyannote)": []}
tahap, mulai = None, None
for baris in Path(a.log).read_text(encoding="utf-8", errors="replace").splitlines():
    m = re.match(r"\[(\d\d:\d\d:\d\d)\] (.*)", baris)
    if not m:
        continue
    t = datetime.combine(tanggal, datetime.strptime(m.group(1), "%H:%M:%S").time())
    if t < sampel[0][0] - timedelta(hours=12):  # lewat tengah malam
        t += timedelta(days=1)
    isi = m.group(2)
    baru = "Speech-to-text (Whisper)" if isi.startswith("transkripsi dengan") else (
        "Pengenal pembicara (pyannote)" if isi.startswith("diarization") else None)
    if baru or isi.startswith("selesai ->"):
        if tahap:
            rentang[tahap].append((mulai, t))
        tahap, mulai = baru, t
if tahap:  # tahap yang masih berjalan dihitung sampai sampel terakhir
    rentang[tahap].append((mulai, sampel[-1][0] + timedelta(seconds=1)))


def ringkas(nama, data):
    if not data:
        return None
    util = [s[1] for s in data]
    mem = [s[2] for s in data]
    daya = [s[4] for s in data if s[4] is not None]
    return {
        "tahap": nama,
        "detik": len(data),
        "util_rata": statistics.mean(util),
        "util_median": statistics.median(util),
        "util_maks": max(util),
        "vram_rata": statistics.mean(mem) / 1024,
        "vram_maks": max(mem) / 1024,
        "vram_total": data[0][3] / 1024,
        "daya_rata": statistics.mean(daya) if daya else None,
        "suhu_maks": max(s[5] for s in data),
    }


hasil = []
for nama, daftar in rentang.items():
    data = [s for s in sampel if any(m <= s[0] < sel for m, sel in daftar)]
    r = ringkas(nama, data)
    if r:
        hasil.append(r)
semua = [s for s in sampel if any(m <= s[0] < sel for d in rentang.values() for m, sel in d)]
r = ringkas("Selama proses (gabungan)", semua)
if r:
    hasil.append(r)

print(f"Data: {len(sampel)} sampel ({sampel[0][0]:%H:%M:%S} - {sampel[-1][0]:%H:%M:%S}), 1 sampel/detik\n")
print(f"{'Tahap':32} {'Durasi':>8} {'GPU rata':>9} {'median':>7} {'maks':>5} {'VRAM rata':>10} {'VRAM maks':>10} {'Daya':>7} {'Suhu maks':>9}")
for r in hasil:
    daya = f"{r['daya_rata']:.0f} W" if r["daya_rata"] is not None else "-"
    print(f"{r['tahap']:32} {r['detik'] / 60:>6.1f} m {r['util_rata']:>8.0f}% {r['util_median']:>6.0f}% {r['util_maks']:>4.0f}% "
          f"{r['vram_rata']:>6.1f} GB {r['vram_maks']:>6.1f} GB {daya:>7} {r['suhu_maks']:>7.0f} C")
if hasil:
    print(f"\nVRAM total: {hasil[0]['vram_total']:.1f} GB")
