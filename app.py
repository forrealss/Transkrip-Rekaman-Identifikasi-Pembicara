"""Tahap 6: tampilan web lokal dengan Gradio.

Jalankan:  .venv\\Scripts\\python app.py   lalu buka http://127.0.0.1:7860
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import gradio as gr  # noqa: E402

from transkrip.asr import UKURAN_MODEL  # noqa: E402
from transkrip.pipeline import proses  # noqa: E402


def jalankan(path_audio, model, jumlah, bersihkan, pakai_prompt, progress=gr.Progress()):
    if not path_audio:
        raise gr.Error("Upload rekaman dulu.")
    teks, path_txt, _ = proses(
        path_audio,
        ukuran_model=model,
        num_speakers=int(jumlah) or None,
        bersihkan=bersihkan,
        pakai_prompt=pakai_prompt,
        progres=lambda f, pesan: progress(f, desc=pesan),
    )
    return teks, str(path_txt)


with gr.Blocks(title="Transkrip Rekaman") as demo:
    gr.Markdown(
        "## Transkrip Rekaman + Pembicara\n"
        "`kata(?)` = model kurang yakin · `[tidak jelas: ...]` = bagian meragukan · "
        "`[tidak terdengar ~Ns]` = ada yang bicara tapi tidak tertangkap. Cek dengan mendengar ulang."
    )
    with gr.Row():
        with gr.Column(scale=1):
            audio = gr.Audio(label="Rekaman", type="filepath", sources=["upload"])
            model = gr.Dropdown(UKURAN_MODEL, value="large-v3", label="Model Whisper")
            jumlah = gr.Number(value=0, precision=0, minimum=0, label="Jumlah pembicara (0 = otomatis)")
            bersihkan = gr.Checkbox(label="Bersihkan audio (kurangi noise, ratakan volume)")
            pakai_prompt = gr.Checkbox(label="Petunjuk kosakata (closing, surat jalan, PO, ...)")
            tombol = gr.Button("Proses", variant="primary")
        with gr.Column(scale=2):
            hasil = gr.Textbox(label="Transkrip", lines=28, buttons=["copy"])
            unduh = gr.File(label="Unduh .txt")
    tombol.click(jalankan, [audio, model, jumlah, bersihkan, pakai_prompt], [hasil, unduh])

if __name__ == "__main__":
    demo.queue().launch(server_name="127.0.0.1", server_port=7860)
