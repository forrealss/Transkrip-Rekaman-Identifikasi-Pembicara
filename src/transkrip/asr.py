"""Tahap 2: suara -> teks dengan faster-whisper.

Ukuran model (makin besar = makin tepat, makin lambat, makin boros VRAM):
  tiny, base, small, medium, large-v3-turbo, large-v3
Untuk bahasa Indonesia dan audio yang kurang jelas, large-v3 paling tepat.
large-v3-turbo jauh lebih cepat dengan akurasi sedikit di bawahnya.
"""
from .gpu import pilih_device, siapkan_dll

UKURAN_MODEL = ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"]

PROMPT_ETIRA = (
    "Wawancara kebutuhan sistem di PT Etira, membahas proses kerja divisi: "
    "sales, penanaman, accounting, finance, closing, surat jalan, invoice, PO, stok, laporan."
)


def muat_model(ukuran="large-v3"):
    siapkan_dll()
    from faster_whisper import WhisperModel

    device, compute_type = pilih_device()
    return WhisperModel(ukuran, device=device, compute_type=compute_type)


def transkripsi(model, path_wav, bahasa="id", prompt=None, progres=None):
    """Kembalikan (list segmen, info). Tiap segmen menyimpan teks, waktu, skor keyakinan, dan per kata."""
    import soundfile as sf

    # WAV sudah 16 kHz mono (Tahap 1), jadi langsung dibaca jadi array. Ini sekaligus
    # menghindari dekoder PyAV bawaan faster-whisper yang versinya kadang tidak cocok.
    data, sr = sf.read(str(path_wav), dtype="float32")
    if sr != 16000 or data.ndim != 1:
        raise ValueError(f"{path_wav} harus WAV 16 kHz mono (pakai audio.ke_wav dulu)")
    segments, info = model.transcribe(
        data,
        language=bahasa,
        beam_size=5,
        vad_filter=True,  # lewati bagian hening -> mengurangi halusinasi
        # Ambang default VAD (0.5) membuang ucapan pelan/jauh di rekaman wawancara Etira.
        # 0.3 terbukti menangkap jauh lebih banyak kalimat tanpa menambah halusinasi.
        vad_parameters={"threshold": 0.3, "min_silence_duration_ms": 500, "speech_pad_ms": 400},
        word_timestamps=True,  # waktu per kata, dipakai saat mencocokkan pembicara
        condition_on_previous_text=False,  # cegah pengulangan berantai di audio bising
        # Kalau ada hening > 2 detik di sekitar teks yang dicurigai halusinasi, lewati.
        hallucination_silence_threshold=2.0,
        # Petunjuk kosakata/topik. Membantu istilah (closing, surat jalan), tapi pada audio
        # yang sangat buruk bisa mendorong model "mengarang" -> default tidak dipakai.
        initial_prompt=prompt,
    )
    hasil = []
    # `segments` adalah generator: transkripsi baru berjalan saat diiterasi.
    for s in segments:
        hasil.append(
            {
                "mulai": s.start,
                "selesai": s.end,
                "teks": s.text.strip(),
                "avg_logprob": s.avg_logprob,
                "no_speech_prob": s.no_speech_prob,
                "compression_ratio": s.compression_ratio,
                "kata": [
                    {"mulai": w.start, "selesai": w.end, "kata": w.word, "prob": w.probability}
                    for w in (s.words or [])
                ],
            }
        )
        if progres:
            progres(s.end / info.duration if info.duration else 0)
    return hasil, info
