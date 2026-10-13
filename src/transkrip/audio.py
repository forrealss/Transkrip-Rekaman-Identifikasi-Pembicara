"""Tahap 1 (dan 7): menyiapkan audio dengan ffmpeg.

Model pengenal suara bekerja dengan WAV 16 kHz mono:
- 16 kHz  : 16.000 sampel per detik, cukup untuk suara manusia.
- mono    : satu kanal; stereo digabung jadi satu.
"""
import glob
import json
import os
import shutil
import subprocess
from pathlib import Path

# Filter pembersih (Tahap 7). Bisa dimatikan karena kadang malah menurunkan akurasi.
#   highpass 80 Hz   : buang dengung/getaran frekuensi rendah
#   lowpass 7600 Hz  : buang desis frekuensi tinggi (di atas batas 16 kHz/2)
#   afftdn           : peredam noise latar berbasis FFT
#   loudnorm         : ratakan volume (suara pelan jadi lebih keras)
FILTER_BERSIHKAN = "highpass=f=80,lowpass=f=7600,afftdn=nf=-25,loudnorm"

EKSTENSI_AUDIO = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac", ".wma", ".mp4", ".mkv", ".webm", ".3gp", ".amr"}


def cari_ffmpeg(nama="ffmpeg"):
    """Cari ffmpeg di PATH; kalau baru dipasang lewat winget, PATH terminal lama belum ter-update."""
    ketemu = shutil.which(nama)
    if ketemu:
        return ketemu
    pola = os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\{nama}.exe")
    hasil = glob.glob(pola)
    if hasil:
        return hasil[0]
    raise FileNotFoundError(f"{nama} tidak ditemukan. Pasang dengan: winget install Gyan.FFmpeg")


def _jalankan(args):
    hasil = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if hasil.returncode != 0:
        raise RuntimeError(f"ffmpeg gagal:\n{hasil.stderr[-2000:]}")
    return hasil


def ke_wav(src, dst, bersihkan=False, mulai=None, durasi=None):
    """Ubah file audio apa pun jadi WAV 16 kHz mono. Opsional: potong dan bersihkan."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = [cari_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"]
    if mulai is not None:
        args += ["-ss", str(mulai)]
    args += ["-i", str(src)]
    if durasi is not None:
        args += ["-t", str(durasi)]
    args += ["-vn", "-ac", "1", "-ar", "16000"]
    if bersihkan:
        args += ["-af", FILTER_BERSIHKAN]
    args += ["-c:a", "pcm_s16le", str(dst)]
    _jalankan(args)
    return dst


def potong(src, dst, mulai=0, durasi=120):
    """Ambil potongan pendek (default 2 menit pertama) sebagai bahan uji cepat."""
    return ke_wav(src, dst, mulai=mulai, durasi=durasi)


def durasi_detik(path):
    hasil = _jalankan([cari_ffmpeg("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(hasil.stdout)["format"]["duration"])


def volume_rata(path):
    """Rata-rata volume (dB). Ucapan normal sekitar -20 s.d. -28 dB; di bawah -35 dB = sangat pelan."""
    hasil = subprocess.run(
        [cari_ffmpeg(), "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for baris in hasil.stderr.splitlines():
        if "mean_volume:" in baris:
            return float(baris.split("mean_volume:")[1].split("dB")[0])
    return None


def muat_waveform(path_wav):
    """Muat WAV jadi tensor (1, n_sampel) untuk pyannote, tanpa bergantung pada torchcodec."""
    import soundfile as sf
    import torch

    data, sr = sf.read(str(path_wav), dtype="float32", always_2d=True)
    waveform = torch.from_numpy(data.T.copy())  # (kanal, sampel)
    return {"waveform": waveform, "sample_rate": sr}
