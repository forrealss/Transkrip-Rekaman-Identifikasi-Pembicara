"""Tahap 3: siapa bicara kapan (speaker diarization) dengan pyannote.audio.

Hasilnya bukan teks, melainkan interval: (mulai, selesai, "SPEAKER_00").
Butuh token Hugging Face (HF_TOKEN di file .env) dan sudah menyetujui
syarat model di halaman Hugging Face-nya.
"""
import os

from dotenv import load_dotenv

from .audio import muat_waveform

MODEL_DIARIZATION = "pyannote/speaker-diarization-community-1"


def ambil_token():
    load_dotenv()
    token = os.getenv("HF_TOKEN", "").strip()
    if not token or token.startswith("hf_xxx"):
        raise RuntimeError("HF_TOKEN belum diisi di file .env (lihat .env.example).")
    return token


def _izinkan_tf32():
    """pyannote mematikan TF32 demi hasil yang bisa diulang persis sama.

    Di GPU RTX (Ampere ke atas) itu membuat tahap embedding ~6x lebih lambat.
    Uji di rekaman Etira: hasil pembicara praktis sama, waktu 34,6 detik -> 6,0 detik.
    """
    import pyannote.audio.core.inference as inference
    import pyannote.audio.core.pipeline as core_pipeline
    import torch

    inference.fix_reproducibility = lambda device: None
    core_pipeline.fix_reproducibility = lambda device: None
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True


def muat_pipeline():
    import torch
    from pyannote.audio import Pipeline

    _izinkan_tf32()

    pipeline = Pipeline.from_pretrained(MODEL_DIARIZATION, token=ambil_token())
    if pipeline is None:
        raise RuntimeError(
            f"Gagal memuat {MODEL_DIARIZATION}. Pastikan syarat model sudah disetujui di "
            f"https://huggingface.co/{MODEL_DIARIZATION}"
        )
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
    return pipeline


def diarisasi(pipeline, path_wav, num_speakers=None, min_speakers=None, max_speakers=None):
    """Kembalikan list (mulai, selesai, label) terurut waktu."""
    opsi = {}
    if num_speakers:
        opsi["num_speakers"] = int(num_speakers)
    else:
        if min_speakers:
            opsi["min_speakers"] = int(min_speakers)
        if max_speakers:
            opsi["max_speakers"] = int(max_speakers)

    keluaran = pipeline(muat_waveform(path_wav), **opsi)
    # pyannote 4 mengembalikan objek berisi beberapa anotasi; versi 3 langsung Annotation.
    # `exclusive_speaker_diarization` tidak punya bicara bertumpuk, jadi lebih mudah dicocokkan ke teks.
    anotasi = getattr(keluaran, "exclusive_speaker_diarization", None)
    if anotasi is None:
        anotasi = getattr(keluaran, "speaker_diarization", keluaran)

    return [(turn.start, turn.end, label) for turn, _, label in anotasi.itertracks(yield_label=True)]
