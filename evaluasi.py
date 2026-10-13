"""Ukur AKURASI SEBENARNYA dengan membandingkan ke transkrip manual (kunci jawaban).

Langkah:
  1. Potong 2-3 menit rekaman yang mewakili (jangan yang paling bagus/paling jelek saja):
       python latihan/01_siapkan_audio.py "assets/Recording (9).m4a" --mulai 300 --durasi 180 --keluar work/eval_rec9.wav
  2. Dengarkan potongan itu, ketik apa yang diucapkan APA ADANYA ke file teks:
       referensi/eval_rec9.txt
     (tanpa nama pembicara/waktu; tanda baca dan huruf besar tidak berpengaruh)
  3. Jalankan, bisa sekaligus membandingkan beberapa setelan:
       python evaluasi.py work/eval_rec9.wav referensi/eval_rec9.txt
       python evaluasi.py work/eval_rec9.wav referensi/eval_rec9.txt --model large-v3 large-v3-turbo --bersihkan --prompt

WER (Word Error Rate) = (kata salah + kata hilang + kata tambahan) / jumlah kata referensi.
Akurasi = 100% - WER. Sebagai patokan: WER < 15% bagus, 15-30% cukup, > 30% berat.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from transkrip import asr, audio, kualitas  # noqa: E402
from transkrip.gabung import halusinasi  # noqa: E402
from transkrip.gpu import bebaskan_vram  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("audio", help="potongan WAV 16 kHz mono (dari latihan/01_siapkan_audio.py)")
ap.add_argument("referensi", help="file .txt berisi transkrip manual")
ap.add_argument("--model", nargs="+", default=["large-v3"], choices=asr.UKURAN_MODEL)
ap.add_argument("--bersihkan", action="store_true", help="uji juga versi audio yang dibersihkan")
ap.add_argument("--prompt", action="store_true", help="uji juga dengan petunjuk kosakata")
a = ap.parse_args()

referensi = Path(a.referensi).read_text(encoding="utf-8")

varian_audio = [("asli", Path(a.audio))]
if a.bersihkan:
    p = Path(a.audio).with_name(Path(a.audio).stem + "_bersih.wav")
    audio.ke_wav(a.audio, p, bersihkan=True)
    varian_audio.append(("bersih", p))
varian_prompt = [("tanpa prompt", None)] + ([("prompt", asr.PROMPT_ETIRA)] if a.prompt else [])

hasil = []
for ukuran in a.model:
    model = asr.muat_model(ukuran)
    for nama_audio, path in varian_audio:
        for nama_prompt, prompt in varian_prompt:
            t = time.time()
            segmen, _ = asr.transkripsi(model, path, prompt=prompt)
            teks = " ".join(s["teks"] for s in segmen if not halusinasi(s))
            skor = kualitas.wer(referensi, teks)
            label = f"{ukuran} | audio {nama_audio} | {nama_prompt}"
            hasil.append((label, skor, time.time() - t))
            print(f"\n=== {label}\n{teks}")
    del model
    bebaskan_vram()

print("\n\nHASIL (diurutkan dari yang terbaik)")
print(f"{'Setelan':52}  {'Akurasi':>7}  {'WER':>5}  {'Salah':>5}  {'Hilang':>6}  {'Tambah':>6}  {'Waktu':>6}")
for label, s, dt in sorted(hasil, key=lambda x: x[1]["wer"]):
    print(
        f"{label:52}  {s['akurasi']:>7.0%}  {s['wer']:>5.0%}  {s['salah_ganti']:>5}  {s['hilang']:>6}  {s['tambahan']:>6}  {dt:>5.0f}s"
    )
print(f"\nJumlah kata referensi: {hasil[0][1]['kata_referensi']}")

from transkrip.gpu import info_sistem  # noqa: E402
from transkrip.grafik import grafik_evaluasi  # noqa: E402

s = info_sistem()
print("\nSpesifikasi:")
for kunci, nilai in s.items():
    print(f"  {kunci:16}: {nilai}")
path_grafik = grafik_evaluasi(
    hasil, ROOT / "output" / f"_grafik_evaluasi_{Path(a.audio).stem}.png", f"Akurasi per setelan - {Path(a.audio).name}",
    catatan=f"Perangkat: {s['GPU']} · {s['CPU']} · RAM {s['RAM']} · faster-whisper {s['faster-whisper']}",
)
print(f"Grafik: {path_grafik}")
