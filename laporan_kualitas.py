"""Ringkasan kualitas semua transkrip di output/ -> output/_laporan_kualitas.txt + _grafik_kualitas.png

Contoh:
  python laporan_kualitas.py

Nilai di sini PERKIRAAN (tanpa kunci jawaban). Untuk akurasi sebenarnya pakai evaluasi.py.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from transkrip import kualitas  # noqa: E402
from transkrip.gpu import info_sistem  # noqa: E402
from transkrip.pipeline import FOLDER_OUTPUT  # noqa: E402


def baca_semua():
    files = {}
    # output/*.json = format lama, output/data/*.json = format baru (yang baru menang)
    for p in list(FOLDER_OUTPUT.glob("*.json")) + list((FOLDER_OUTPUT / "data").glob("*.json")):
        files[p.stem] = p
    return [files[k] for k in sorted(files, key=str.lower)]


def ke_detik(hhmmss):
    try:
        j, m, d = (int(x) for x in str(hhmmss).split(":"))
        return j * 3600 + m * 60 + d
    except ValueError:
        return None


def waktu_proses(data):
    """Detik proses; dari blok 'kecepatan' (format baru) atau teks 'Waktu proses' (format lama)."""
    if "kecepatan" in data:
        return data["kecepatan"]["detik_proses"]
    cocok = re.match(r"(\d+)", str(data.get("info", {}).get("Waktu proses", "")))
    return int(cocok.group(1)) if cocok else None


def format_menit(detik):
    return "-" if detik is None else (f"{detik / 60:.1f} mnt" if detik >= 60 else f"{detik} dtk")


def main():
    baris_laporan, sistem, model = [], None, set()
    total_rekaman = total_proses = 0
    for p in baca_semua():
        data = json.loads(p.read_text(encoding="utf-8"))
        info = data.get("info", {})
        sistem = sistem or data.get("sistem")
        if info.get("Model"):
            model.add(str(info["Model"]))
        vol_teks = str(info.get("Volume rata-rata", "?")).split(" (")[0]
        kosong = "REKAMAN KOSONG" in str(info.get("Status", "")) or (vol_teks.endswith("dB") and float(vol_teks.split()[0]) < -70)
        if kosong:
            k = {"nilai": "Kosong", "skor": 0, "cakupan": 0, "yakin": 0, "detik_tidak_terdengar": 0, "jumlah_kata": 0}
        else:
            k = kualitas.perkiraan(data.get("segmen_whisper") or [], data.get("interval_pembicara") or [], data.get("baris") or [])
        dur = ke_detik(info.get("Durasi"))
        proses = waktu_proses(data)
        if dur and proses and not kosong:
            total_rekaman += dur
            total_proses += proses
        baris_laporan.append((p.stem, info.get("Durasi", "?"), vol_teks, k, proses, dur))

    # Hasil lama belum menyimpan spesifikasi; semuanya diproses di komputer ini, jadi pakai info saat ini.
    sistem = sistem or info_sistem()

    lebar = max([len(n) for n, *_ in baris_laporan] + [10])
    judul = (f"{'Rekaman':{lebar}}  {'Durasi':8}  {'Volume':9}  {'Nilai':6}  {'Skor':>5}  {'Tertangkap':>10}  "
             f"{'Yakin':>6}  {'Tdk dengar':>10}  {'Kata':>6}  {'Proses':>9}  {'Kecepatan':>9}")
    isi = [
        "LAPORAN KUALITAS TRANSKRIP (perkiraan otomatis, bukan akurasi pasti)",
        "",
        "SPESIFIKASI",
        *[f"  {kunci:16}: {nilai}" for kunci, nilai in sistem.items()],
        *[f"  {'Model':16}: {m}" for m in sorted(model)],
        "",
        "KETERANGAN",
        "  Tertangkap  = % waktu orang bicara yang berhasil jadi teks",
        "  Yakin       = % kata yang tidak ditandai (?) / [tidak jelas]",
        "  Skor        = Tertangkap x Yakin.  Baik >= 70%, Cukup >= 50%, Kurang >= 30%, Buruk < 30%",
        "  Kosong      = rekaman tanpa suara sama sekali (cek mikrofon saat merekam)",
        "  Kecepatan   = durasi rekaman / waktu proses (mis. 10x = 1 jam rekaman selesai dalam 6 menit)",
        "",
        judul,
        "-" * len(judul),
    ]
    for nama, durasi, vol, k, proses, dur in baris_laporan:
        cepat = f"{dur / proses:.0f}x" if dur and proses and k["nilai"] != "Kosong" else "-"
        isi.append(
            f"{nama:{lebar}}  {durasi:8}  {vol:9}  {k['nilai']:6}  {k['skor']:>5.0%}  {k['cakupan']:>10.0%}  "
            f"{k['yakin']:>6.0%}  {str(k['detik_tidak_terdengar']) + 's':>10}  {k['jumlah_kata']:>6}  "
            f"{format_menit(proses):>9}  {cepat:>9}"
        )
    if total_proses:
        isi += ["", f"Total: {total_rekaman / 3600:.1f} jam rekaman berisi suara diproses dalam "
                    f"{total_proses / 60:.0f} menit ({total_rekaman / total_proses:.0f}x lebih cepat dari durasinya)."]
    teks = "\n".join(isi) + "\n"
    path = FOLDER_OUTPUT / "_laporan_kualitas.txt"
    path.write_text(teks, encoding="utf-8")
    print(teks)
    print(f"Tersimpan: {path}")

    from transkrip.grafik import grafik_kualitas

    if baris_laporan:
        catatan = f"Perangkat: {sistem['GPU']} · {sistem['CPU']} · RAM {sistem['RAM']}"
        if model:
            catatan += f"\nModel: {' / '.join(sorted(model))}"
        path_grafik = grafik_kualitas([b[:4] for b in baris_laporan], FOLDER_OUTPUT / "_grafik_kualitas.png", catatan)
        print(f"Grafik   : {path_grafik}")


if __name__ == "__main__":
    main()
