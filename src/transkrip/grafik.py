"""Grafik kualitas & akurasi (matplotlib -> PNG).

Aturan tampilan:
- satu sumbu saja, nilai 0-100%
- warna nilai Baik/Cukup/Kurang/Buruk selalu disertai tulisan (tidak mengandalkan warna saja)
- garis bantu tipis, label teks pakai warna tinta, bukan warna batang
"""
import matplotlib

matplotlib.use("Agg")  # tanpa jendela, langsung ke file
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

PERMUKAAN = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
REDUP = "#898781"
GRID = "#e1e0d9"
SUMBU = "#c3c2b7"
SERI = ["#2a78d6", "#eb6834"]  # biru, oranye (lolos uji buta warna)
STATUS = {
    "Baik": "#0ca30c",
    "Cukup": "#fab219",
    "Kurang": "#ec835a",
    "Buruk": "#d03b3b",
    "Kosong": "#c3c2b7",
    "Tanpa ucapan": "#c3c2b7",
}
TANPA_DATA = ("Kosong", "Tanpa ucapan")
BATAS_NILAI = [(0.30, "Kurang"), (0.50, "Cukup"), (0.70, "Baik")]


def _gaya(ax):
    ax.set_facecolor(PERMUKAAN)
    for sisi in ("top", "right", "left"):
        ax.spines[sisi].set_visible(False)
    ax.spines["bottom"].set_color(SUMBU)
    ax.tick_params(colors=TINTA_2, labelsize=9, length=0)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0, 1.0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _rapikan_nama(nama, maks=28):
    return nama if len(nama) <= maks else nama[: maks - 1] + "â€¦"


def grafik_kualitas(baris, path, catatan=""):
    """baris: list (nama, durasi, volume, dict_kualitas). Simpan 2 panel ke `path`."""
    baris = list(reversed(baris))  # matplotlib menggambar barh dari bawah
    nama = [_rapikan_nama(n) for n, *_ in baris]
    k = [x[3] for x in baris]
    y = range(len(baris))
    tinggi = max(3.0, 0.42 * len(baris) + 1.4)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, tinggi), sharey=True, facecolor=PERMUKAAN,
                                   gridspec_kw={"width_ratios": [1, 1.15], "wspace": 0.08})

    # Panel 1: skor keseluruhan, warna = nilai (+ tulisan nilai di ujung batang)
    _gaya(ax1)
    for batas, label in BATAS_NILAI:
        ax1.axvline(batas, color=SUMBU, linewidth=0.8, linestyle=(0, (3, 3)), zorder=1)
        ax1.text(batas, len(baris) - 0.35, f" {label}", color=REDUP, fontsize=8, va="bottom")
    for i, x in zip(y, k):
        ax1.barh(i, max(x["skor"], 0.004), height=0.6, color=STATUS[x["nilai"]], zorder=2)
        ax1.text(max(x["skor"], 0) + 0.012, i, f"{x['skor']:.0%}  {x['nilai']}", va="center",
                 color=TINTA if x["nilai"] not in TANPA_DATA else REDUP, fontsize=9)
    ax1.set_yticks(list(y), nama, color=TINTA)
    # ruang ekstra di kanan supaya tulisan "95%  Baik" tidak terpotong panel sebelah
    ax1.set_xlim(0, 1.22)
    ax1.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax1.spines["bottom"].set_bounds(0, 1.0)
    ax1.set_title("Skor kualitas (perkiraan)", loc="left", color=TINTA, fontsize=11, fontweight="bold", pad=18)

    # Panel 2: dua komponen skor, berdampingan
    _gaya(ax2)
    h = 0.34
    for j, (kunci, label) in enumerate([("cakupan", "Ucapan tertangkap"), ("yakin", "Kata yakin")]):
        geser = (0.5 - j) * h + (0.02 if j == 0 else -0.02)
        ax2.barh([i + geser for i in y], [max(x[kunci], 0.004) for x in k], height=h - 0.04,
                 color=SERI[j], label=label, zorder=2)
    for i, x in zip(y, k):
        if x["nilai"] not in TANPA_DATA:
            ax2.text(x["cakupan"] + 0.012, i + h / 2, f"{x['cakupan']:.0%}", va="center", color=TINTA_2, fontsize=8)
            ax2.text(x["yakin"] + 0.012, i - h / 2, f"{x['yakin']:.0%}", va="center", color=TINTA_2, fontsize=8)
        else:
            ax2.text(0.012, i, "tidak ada suara" if x["nilai"] == "Kosong" else "tidak ada ucapan",
                     va="center", color=REDUP, fontsize=8)
    ax2.set_title("Komponen skor", loc="left", color=TINTA, fontsize=11, fontweight="bold", pad=18)
    ax2.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=TINTA_2,
               bbox_to_anchor=(1.0, 1.0), ncol=2, borderaxespad=0.2)

    keterangan = "Skor = ucapan tertangkap x kata yakin. Perkiraan otomatis; akurasi pasti -> evaluasi.py"
    fig.text(0.01, -0.01, keterangan + ("\n" + catatan if catatan else ""), color=REDUP, fontsize=8, va="top")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=PERMUKAAN)
    plt.close(fig)
    return path


def grafik_evaluasi(hasil, path, judul="Akurasi per setelan", catatan=""):
    """hasil: list (label, dict_wer, detik). Batang akurasi, diurutkan dari yang terbaik."""
    hasil = sorted(hasil, key=lambda x: x[1]["akurasi"])  # terbaik di atas (barh dari bawah)
    y = range(len(hasil))
    fig, ax = plt.subplots(figsize=(10, max(2.6, 0.65 * len(hasil) + 1.2)), facecolor=PERMUKAAN)
    _gaya(ax)
    for batas, label in [(0.70, "cukup"), (0.85, "bagus")]:
        ax.axvline(batas, color=SUMBU, linewidth=0.8, linestyle=(0, (3, 3)), zorder=1)
        ax.text(batas, len(hasil) - 0.4, f" {label}", color=REDUP, fontsize=8, va="bottom")
    terbaik = len(hasil) - 1
    for i, (label, s, dt) in zip(y, hasil):
        ax.barh(i, max(s["akurasi"], 0.004), height=0.6, color=SERI[0] if i == terbaik else "#86b6ef", zorder=2)
        ax.text(s["akurasi"] + 0.012, i, f"{s['akurasi']:.0%}", va="center", color=TINTA, fontsize=10,
                fontweight="bold" if i == terbaik else "normal")
    # rincian kesalahan ditaruh di bawah nama setelan, bukan di area grafik
    ax.set_yticks(
        list(y),
        [f"{label}\nsalah {s['salah_ganti']} Â· hilang {s['hilang']} Â· tambah {s['tambahan']} Â· {dt:.0f} detik"
         for label, s, dt in hasil],
        color=TINTA, fontsize=9,
    )
    ax.set_title(judul, loc="left", color=TINTA, fontsize=11, fontweight="bold", pad=18)
    keterangan = f"Akurasi = 100% - WER, dari {hasil[0][1]['kata_referensi']} kata referensi. Batang tua = setelan terbaik."
    fig.text(0.01, -0.01, keterangan + ("\n" + catatan if catatan else ""), color=REDUP, fontsize=8, va="top")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=PERMUKAAN)
    plt.close(fig)
    return path
