"""Merangkai Tahap 1-4 jadi satu fungsi `proses()`.

Dipakai bersama oleh proses_semua.py (batch) dan app.py (Gradio).
Model Whisper dan pyannote dijalankan BERGANTIAN dan VRAM dibebaskan di antaranya,
supaya muat di GPU 6 GB.
"""
import time
from pathlib import Path

from . import asr, audio, diarize, gabung, kualitas
from .gpu import bebaskan_vram, info_perangkat, info_sistem, pilih_device

ROOT = Path(__file__).resolve().parents[2]
FOLDER_WORK = ROOT / "work"
FOLDER_OUTPUT = ROOT / "output"
# Di bawah ini dianggap tidak ada suara sama sekali (hening digital = -91 dB).
AMBANG_KOSONG_DB = -70


def _cetak(pesan):
    print(f"[{time.strftime('%H:%M:%S')}] {pesan}", flush=True)


def proses(
    path_audio,
    ukuran_model="large-v3",
    num_speakers=None,
    bersihkan=False,
    pakai_prompt=False,
    folder_output=FOLDER_OUTPUT,
    nama=None,
    progres=None,
):
    """Rekaman -> transkrip berlabel pembicara. Kembalikan (teks, path_txt, path_json).

    progres(fraksi, pesan) opsional, dipakai Gradio untuk progress bar.
    """
    path_audio = Path(path_audio)
    nama = nama or path_audio.stem
    lapor = progres or (lambda f, p: None)
    t_awal = time.time()

    # Tahap 1: siapkan audio
    lapor(0.02, "Menyiapkan audio")
    _cetak(f"{path_audio.name}: konversi ke WAV 16 kHz mono{' + bersihkan' if bersihkan else ''}")
    path_wav = audio.ke_wav(path_audio, FOLDER_WORK / f"{nama}{'_bersih' if bersihkan else ''}.wav", bersihkan=bersihkan)
    durasi = audio.durasi_detik(path_wav)
    volume = audio.volume_rata(path_wav)

    # Rekaman hening total (mis. mikrofon tidak aktif): -91 dB = tidak ada sinyal sama sekali.
    if volume is not None and volume < AMBANG_KOSONG_DB:
        _cetak(f"  volume {volume:.1f} dB -> REKAMAN KOSONG, dilewati")
        header = {
            "File": path_audio.name,
            "Durasi": gabung.format_waktu(durasi),
            "Volume rata-rata": f"{volume:.1f} dB",
            "Status": "REKAMAN KOSONG - tidak ada suara sama sekali (cek apakah mikrofon aktif saat merekam)",
        }
        path_txt, path_json = gabung.simpan([], folder_output, nama, header, [], [], ekstra={"sistem": info_sistem()})
        lapor(1.0, "Rekaman kosong")
        return gabung.ke_teks([], header), path_txt, path_json

    # Tahap 2: transkripsi
    lapor(0.05, f"Memuat model Whisper {ukuran_model}")
    _cetak(f"transkripsi dengan {ukuran_model} (durasi {gabung.format_waktu(durasi)})")
    t = time.time()
    model = asr.muat_model(ukuran_model)
    prompt = asr.PROMPT_ETIRA if pakai_prompt else None
    segmen, _ = asr.transkripsi(model, path_wav, prompt=prompt, progres=lambda f: lapor(0.05 + 0.65 * f, "Transkripsi"))
    del model
    bebaskan_vram()
    t_asr = time.time() - t
    _cetak(f"  {len(segmen)} segmen, {t_asr:.0f} detik")

    # Tahap 3: diarization
    lapor(0.72, "Mengenali pembicara")
    _cetak("diarization pyannote")
    t = time.time()
    pipeline = diarize.muat_pipeline()
    interval = diarize.diarisasi(pipeline, path_wav, num_speakers=num_speakers)
    del pipeline
    bebaskan_vram()
    t_diar = time.time() - t
    _cetak(f"  {len(interval)} interval, {len({i[2] for i in interval})} pembicara, {t_diar:.0f} detik")

    # Tahap 4: gabung
    lapor(0.95, "Menggabungkan")
    baris = gabung.gabungkan(segmen, interval)
    mutu = kualitas.perkiraan(segmen, interval, baris)
    t_total = max(time.time() - t_awal, 1)
    header = {
        "File": path_audio.name,
        "Durasi": gabung.format_waktu(durasi),
        "Model": f"Whisper {ukuran_model} ({pilih_device()[1]}) + {diarize.MODEL_DIARIZATION}",
        "Audio dibersihkan": "ya" if bersihkan else "tidak",
        "Prompt kosakata": "ya" if pakai_prompt else "tidak",
        "Volume rata-rata": (
            f"{volume:.1f} dB" + (" (SANGAT PELAN - banyak bagian mungkin tidak tertangkap)" if volume < -35 else "")
            if volume is not None
            else "?"
        ),
        "Kualitas (perkiraan)": kualitas.ringkas(mutu),
        "Jumlah pembicara": len({b["pembicara"] for b in baris}),
        "Penanda": (
            "kata(?) = kata kurang yakin; [tidak jelas: ...] = bagian meragukan; "
            "[tidak terdengar ~Ns] = ada yang bicara tapi tidak tertangkap. Cek ulang dengan mendengar"
        ),
        "Jumlah penanda": sum(b["jumlah_ragu"] for b in baris),
        "Waktu proses": (
            f"{t_total:.0f} detik (ASR {t_asr:.0f}, diarization {t_diar:.0f}) = {durasi / t_total:.0f}x lebih cepat dari durasi rekaman"
        ),
        "Perangkat": info_perangkat(),
    }
    path_txt, path_json = gabung.simpan(
        baris, folder_output, nama, header, segmen, interval,
        ekstra={
            "sistem": info_sistem(),
            "kualitas": mutu,
            "kecepatan": {"detik_rekaman": round(durasi), "detik_proses": round(t_total),
                          "detik_asr": round(t_asr), "detik_diarization": round(t_diar)},
        },
    )
    _cetak(f"selesai -> {path_txt}  [{kualitas.ringkas(mutu)}]")
    lapor(1.0, "Selesai")
    return gabung.ke_teks(baris, header), path_txt, path_json
