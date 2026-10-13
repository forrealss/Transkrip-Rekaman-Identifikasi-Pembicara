"""Tahap 4: menggabungkan teks (Tahap 2) dengan pembicara (Tahap 3).

Ide dasarnya:
  1. Tiap KATA punya waktu [mulai, selesai]. Tiap interval pembicara juga.
  2. Kata diberikan ke pembicara yang intervalnya paling banyak tumpang tindih.
  3. Kata-kata berurutan dari orang yang sama digabung jadi satu giliran bicara.
  4. Label SPEAKER_00 diganti "Pembicara 1" sesuai urutan kemunculan.

Ditambah penandaan bagian yang tidak jelas, supaya bisa dicek ulang manual.
"""
import bisect
import json
from pathlib import Path

# --- Ambang penandaan "tidak jelas" (silakan disetel saat Tahap 7) -------------
# Probabilitas kata 0..1. Di bawah ini kata ditulis "kata(?)".
# (0.45 terlalu sensitif: kata umum seperti "iya", "kan", "apa" ikut ditandai.)
AMBANG_KATA = 0.3
# Rata-rata log-probabilitas segmen. Makin negatif = model makin ragu.
AMBANG_LOGPROB = -1.0
# Peluang segmen sebenarnya bukan ucapan (noise yang "ditebak" jadi kata).
AMBANG_NO_SPEECH = 0.6
# Rasio kompresi tinggi = teks berulang-ulang, ciri khas halusinasi Whisper.
AMBANG_KOMPRESI = 2.4
# Jeda (detik) yang memaksa baris baru walaupun pembicaranya sama.
JEDA_BARIS_BARU = 4.0
# Kata dengan overlap 0 boleh ambil pembicara terdekat sejauh ini (detik).
JARAK_MAKS_TERDEKAT = 1.0
# Interval bicara (dari pyannote) sepanjang ini yang hampir tanpa teks -> "[tidak terdengar]".
MIN_TIDAK_TERDENGAR = 2.5
# "Hampir tanpa teks" = bagian interval yang tertutup kata kurang dari ini.
CAKUPAN_MIN = 0.15
# ------------------------------------------------------------------------------

TANPA_PEMBICARA = "?"

# Kalimat yang sering "dikarang" Whisper saat audio hening/bising (warisan data latih subtitle).
KALIMAT_HALUSINASI = {
    "terima kasih",
    "terima kasih telah menonton",
    "terima kasih sudah menonton",
    "terima kasih telah menyaksikan",
    "jangan lupa like dan subscribe",
    "sampai jumpa di video selanjutnya",
    "subtitle by",
}


def overlap(a0, a1, b0, b1):
    """Panjang tumpang tindih dua interval waktu (0 kalau tidak bersentuhan)."""
    return max(0.0, min(a1, b1) - max(a0, b0))


class PencariPembicara:
    """Mencari pembicara untuk rentang waktu tertentu.

    Interval diarization diurutkan menurut waktu mulai, lalu bisect dipakai
    supaya tidak perlu memeriksa semua interval untuk setiap kata
    (rekaman 30 menit bisa punya ribuan kata dan ratusan interval).
    """

    def __init__(self, interval):
        self.interval = sorted(interval)
        self.mulai = [i[0] for i in self.interval]
        # interval terpanjang: interval yang mulai lebih awal dari (t0 - ini) pasti sudah selesai sebelum t0
        self.panjang_maks = max((i[1] - i[0] for i in self.interval), default=0)

    def cari(self, t0, t1):
        if not self.interval:
            return TANPA_PEMBICARA
        # Kandidat: interval yang mulai sebelum t1 dan belum selesai sebelum t0.
        kanan = bisect.bisect_right(self.mulai, t1)
        kiri = bisect.bisect_left(self.mulai, t0 - self.panjang_maks)
        skor = {}
        for m, s, label in self.interval[kiri:kanan]:
            o = overlap(t0, t1, m, s)
            if o > 0:
                skor[label] = skor.get(label, 0) + o
        if skor:
            return max(skor, key=skor.get)

        # Tidak ada yang tumpang tindih (mis. kata jatuh di celah antar interval):
        # ambil interval terdekat kalau jaraknya masih wajar.
        tengah = (t0 + t1) / 2
        lo = max(0, kanan - 2)
        hi = min(len(self.interval), kanan + 2)
        terdekat, jarak_min = TANPA_PEMBICARA, JARAK_MAKS_TERDEKAT
        for m, s, label in self.interval[lo:hi]:
            jarak = 0 if m <= tengah <= s else min(abs(tengah - m), abs(tengah - s))
            if jarak < jarak_min:
                terdekat, jarak_min = label, jarak
        return terdekat


def segmen_meragukan(seg):
    # no_speech_prob sendiri tidak bisa dipercaya pada rekaman pelan (ucapan asli bisa dapat 0.9),
    # jadi hanya dihitung kalau model juga kurang yakin dengan teksnya.
    return (
        seg["avg_logprob"] < AMBANG_LOGPROB
        or (seg["no_speech_prob"] > AMBANG_NO_SPEECH and seg["avg_logprob"] < AMBANG_LOGPROB / 2)
        or seg["compression_ratio"] > AMBANG_KOMPRESI
    )


def halusinasi(seg):
    """Segmen berisi kalimat khas halusinasi, dan ada tanda bahwa itu bukan ucapan sungguhan.

    "Terima kasih." bisa saja diucapkan sungguhan, jadi hanya dibuang kalau model sendiri
    ragu ada suara (no_speech_prob) atau 1-4 kata itu 'direntang' terlalu lama.
    """
    teks = "".join(c for c in seg["teks"].lower() if c.isalnum() or c == " ").strip()
    if teks not in KALIMAT_HALUSINASI:
        return False
    return seg["no_speech_prob"] > 0.5 or (seg["selesai"] - seg["mulai"]) > 4


def pecah_jadi_kata(segmen, pencari):
    """Ubah segmen Whisper jadi daftar kata yang sudah diberi pembicara."""
    kata_semua = []
    for seg in segmen:
        if halusinasi(seg):
            continue
        ragu = segmen_meragukan(seg)
        if seg["kata"]:
            for w in seg["kata"]:
                kata_semua.append(
                    {
                        "mulai": w["mulai"],
                        "selesai": w["selesai"],
                        # Teks kata dari Whisper sudah membawa spasi di depannya (" barang"),
                        # kecuali potongan sambungan ("-kecil"). Jangan di-strip, supaya
                        # penyambungan nanti tetap benar.
                        "kata": w["kata"],
                        "prob": w["prob"],
                        "segmen_ragu": ragu,
                        "pembicara": pencari.cari(w["mulai"], w["selesai"]),
                    }
                )
        else:
            # Fallback: tidak ada data per kata -> satu segmen dianggap satu "kata".
            kata_semua.append(
                {
                    "mulai": seg["mulai"],
                    "selesai": seg["selesai"],
                    "kata": " " + seg["teks"],
                    "prob": 1.0,
                    "segmen_ragu": ragu,
                    "pembicara": pencari.cari(seg["mulai"], seg["selesai"]),
                }
            )
    return [k for k in kata_semua if k["kata"].strip()]


def tambah_tidak_terdengar(kata, interval):
    """Sisipkan penanda di tempat pyannote mendengar orang bicara, tapi Whisper tidak menangkap teksnya.

    Untuk tiap interval bicara yang cukup panjang, hitung berapa bagian yang tertutup kata.
    Kalau hampir kosong, sisipkan "[tidak terdengar ~Ns]" atas nama pembicara itu.
    """
    if not interval:
        return kata
    mulai_kata = [k["mulai"] for k in kata]
    penanda = []
    for m, s, label in interval:
        if s - m < MIN_TIDAK_TERDENGAR:
            continue
        # kata yang mungkin bersinggungan dengan [m, s]
        i = max(0, bisect.bisect_left(mulai_kata, m) - 1)
        tertutup = 0.0
        while i < len(kata) and kata[i]["mulai"] < s:
            tertutup += overlap(m, s, kata[i]["mulai"], kata[i]["selesai"])
            i += 1
        if tertutup / (s - m) < CAKUPAN_MIN:
            penanda.append(
                {
                    "mulai": m,
                    "selesai": s,
                    "kata": f" [tidak terdengar ~{round(s - m)}s]",
                    "prob": 1.0,
                    "segmen_ragu": False,
                    "penanda": True,
                    "pembicara": label,
                }
            )
    return sorted(kata + penanda, key=lambda k: k["mulai"])


def haluskan(kata):
    """Kata tunggal yang 'terselip' di tengah dua kata pembicara lain biasanya salah tempel.

    Contoh: A A A [B] A A -> B kemungkinan besar adalah A juga.
    """
    for i in range(1, len(kata) - 1):
        kiri, kanan = kata[i - 1]["pembicara"], kata[i + 1]["pembicara"]
        if kiri == kanan != kata[i]["pembicara"] and kata[i]["selesai"] - kata[i]["mulai"] < 0.6:
            kata[i]["pembicara"] = kiri
    return kata


def kelompokkan(kata):
    """Gabungkan kata berurutan dari pembicara yang sama jadi giliran bicara."""
    giliran = []
    for k in kata:
        akhir = giliran[-1] if giliran else None
        if akhir and akhir["pembicara"] == k["pembicara"] and k["mulai"] - akhir["selesai"] <= JEDA_BARIS_BARU:
            akhir["kata"].append(k)
            akhir["selesai"] = k["selesai"]
        else:
            giliran.append({"pembicara": k["pembicara"], "mulai": k["mulai"], "selesai": k["selesai"], "kata": [k]})
    return giliran


def buat_label(giliran):
    """SPEAKER_xx -> 'Pembicara N' sesuai urutan pertama kali bicara."""
    label = {}
    for g in giliran:
        p = g["pembicara"]
        if p not in label:
            label[p] = "Pembicara ?" if p == TANPA_PEMBICARA else f"Pembicara {sum(1 for x in label if x != TANPA_PEMBICARA) + 1}"
    return label


def teks_giliran(g):
    """Susun teks satu giliran, beri tanda pada bagian yang meragukan.

    - kata dengan probabilitas rendah      -> kata(?)
    - rangkaian kata dari segmen meragukan -> [tidak jelas: ...]
    """
    # Tiap potongan membawa spasinya sendiri di depan (gaya Whisper), jadi cukup disambung.
    bagian, blok_ragu, n_ragu = [], [], 0

    def tutup_blok():
        nonlocal n_ragu
        if blok_ragu:
            bagian.append(f" [tidak jelas: {''.join(blok_ragu).strip()}]")
            blok_ragu.clear()
            n_ragu += 1

    for k in g["kata"]:
        if k.get("penanda"):
            tutup_blok()
            bagian.append(k["kata"])
            n_ragu += 1
            continue
        if k["segmen_ragu"]:
            blok_ragu.append(k["kata"])
            continue
        tutup_blok()
        if k["prob"] < AMBANG_KATA:
            # taruh (?) sebelum tanda baca: "bon(?)," bukan "bon,(?)"
            kata = k["kata"].rstrip(".,?!")
            bagian.append(f"{kata}(?){k['kata'][len(kata):]}")
            n_ragu += 1
        else:
            bagian.append(k["kata"])
    tutup_blok()
    return "".join(bagian).strip(), n_ragu


def format_waktu(detik):
    detik = int(detik)
    return f"{detik // 3600:02d}:{detik % 3600 // 60:02d}:{detik % 60:02d}"


def gabungkan(segmen, interval):
    """Fungsi utama Tahap 4. Kembalikan list baris {waktu, pembicara, teks, ...}."""
    pencari = PencariPembicara(interval)
    kata = haluskan(pecah_jadi_kata(segmen, pencari))
    kata = tambah_tidak_terdengar(kata, interval)
    giliran = kelompokkan(kata)
    label = buat_label(giliran)

    baris = []
    for g in giliran:
        teks, n_ragu = teks_giliran(g)
        baris.append(
            {
                "mulai": round(g["mulai"], 2),
                "selesai": round(g["selesai"], 2),
                "pembicara": label[g["pembicara"]],
                "label_asli": g["pembicara"],
                "teks": teks,
                "jumlah_ragu": n_ragu,
            }
        )
    return baris


def ke_teks(baris, header=None):
    isi = []
    if header:
        isi += [f"# {k}: {v}" for k, v in header.items()]
        isi.append("")
    for b in baris:
        isi.append(f"[{format_waktu(b['mulai'])}] {b['pembicara']}: {b['teks']}")
    return "\n".join(isi) + "\n"


def simpan(baris, folder_output, nama, header=None, segmen=None, interval=None, ekstra=None):
    folder_output = Path(folder_output)
    folder_output.mkdir(parents=True, exist_ok=True)
    path_txt = folder_output / f"{nama}.txt"
    # .json (data teknis) dipisah ke subfolder supaya output/ hanya berisi .txt yang mudah dibaca
    path_json = folder_output / "data" / f"{nama}.json"
    path_json.parent.mkdir(exist_ok=True)
    path_txt.write_text(ke_teks(baris, header), encoding="utf-8")
    path_json.write_text(
        json.dumps(
            {"info": header or {}, **(ekstra or {}), "baris": baris, "segmen_whisper": segmen,
             "interval_pembicara": interval},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path_txt, path_json
