"""Tahap 0: cek apakah semua bahan sudah siap."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)


def cek(nama, fungsi):
    try:
        hasil = fungsi()
        print(f"  OK    {nama}: {hasil}")
    except Exception as e:
        print(f"  GAGAL {nama}: {e}")


def python_versi():
    v = sys.version_info
    if v[:2] not in [(3, 10), (3, 11), (3, 12)]:
        raise RuntimeError(f"{v.major}.{v.minor} - pakai venv Python 3.12 (.venv)")
    return f"{v.major}.{v.minor}.{v.micro}"


def ffmpeg():
    from transkrip.audio import cari_ffmpeg

    return cari_ffmpeg()


def gpu():
    import torch

    if not torch.cuda.is_available():
        return "tidak ada CUDA -> akan memakai CPU (jauh lebih lambat)"
    p = torch.cuda.get_device_properties(0)
    return f"{p.name}, {p.total_memory / 1024**3:.1f} GB VRAM, torch {torch.__version__}"


def ctranslate2_cuda():
    from transkrip.gpu import siapkan_dll

    siapkan_dll()
    import ctranslate2

    n = ctranslate2.get_cuda_device_count()
    if n == 0:
        raise RuntimeError("ctranslate2 tidak melihat GPU")
    return f"{n} GPU, compute types: {sorted(ctranslate2.get_supported_compute_types('cuda'))}"


def hf_token():
    from transkrip.diarize import ambil_token

    t = ambil_token()
    return f"terbaca ({len(t)} karakter)"


def rekaman():
    from transkrip.audio import EKSTENSI_AUDIO

    files = [p.name for p in (ROOT / "assets").glob("*") if p.suffix.lower() in EKSTENSI_AUDIO]
    if not files:
        raise RuntimeError("folder assets/ masih kosong")
    return f"{len(files)} file: {', '.join(files[:5])}{' ...' if len(files) > 5 else ''}"


print("Cek lingkungan:")
cek("Python", python_versi)
cek("ffmpeg", ffmpeg)
cek("GPU (torch)", gpu)
cek("GPU (faster-whisper)", ctranslate2_cuda)
cek("HF_TOKEN", hf_token)
cek("Rekaman", rekaman)
