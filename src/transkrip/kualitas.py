"""Mengukur kualitas transkrip.

Ada dua jenis ukuran:

1. PERKIRAAN (otomatis, tanpa kunci jawaban) -> perkiraan()
   - cakupan : dari seluruh waktu orang bicara (menurut pyannote), berapa persen yang ada teksnya
   - yakin   : dari semua kata, berapa persen yang tidak ditandai (?) / [tidak jelas]
   - skor    : cakupan x yakin -> Baik / Cukup / Kurang / Buruk
   Ini bukan akurasi sebenarnya, tapi bagus untuk membandingkan antar rekaman.

2. AKURASI SEBENARNYA (butuh transkrip manual sebagai kunci jawaban) -> wer()
   WER (Word Error Rate) = (kata salah ganti + kata hilang + kata tambahan) / jumlah kata kunci.
   Akurasi = 100% - WER.
"""
import re
import unicodedata

from . import gabung

NILAI = [(0.70, "Baik"), (0.50, "Cukup"), (0.30, "Kurang"), (0.0, "Buruk")]


# ---------------------------------------------------------------- perkiraan --
def satukan(interval):
    """Gabungkan interval yang tumpang tindih: [(0,3),(2,5),(7,8)] -> [(0,5),(7,8)]."""
    hasil = []
    for m, s in sorted(interval):
        if hasil and m <= hasil[-1][1]:
            hasil[-1][1] = max(hasil[-1][1], s)
        else:
            hasil.append([m, s])
    return hasil


def panjang_irisan(a, b):
    """Total panjang irisan dua daftar interval yang sudah disatukan (dua penunjuk)."""
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        total += gabung.overlap(a[i][0], a[i][1], b[j][0], b[j][1])
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def perkiraan(segmen, interval, baris):
    bicara = satukan([(m, s) for m, s, _ in interval])
    detik_bicara = sum(s - m for m, s in bicara)

    kata = []
    for seg in segmen:
        if gabung.halusinasi(seg):
            continue
        ragu = gabung.segmen_meragukan(seg)
        for w in seg["kata"]:
            kata.append((w["mulai"], w["selesai"], w["prob"], ragu))

    if not kata or detik_bicara == 0:
        return {"detik_bicara": round(detik_bicara), "jumlah_kata": len(kata), "cakupan": 0, "yakin": 0,
                "rata_prob": 0, "detik_tidak_terdengar": 0, "skor": 0,
                # Ada suara tapi tidak ada kata (mis. musik/noise) beda dengan rekaman hening ("Kosong").
                "nilai": "Tanpa ucapan" if not kata else "Buruk"}

    # Kata Whisper cenderung pendek; beri sedikit kelonggaran 0,3 detik di kanan-kiri.
    ruang_kata = satukan([(m - 0.3, s + 0.3) for m, s, _, _ in kata])
    cakupan = min(1.0, panjang_irisan(bicara, ruang_kata) / detik_bicara)
    yakin = sum(1 for _, _, p, r in kata if p >= gabung.AMBANG_KATA and not r) / len(kata)
    tidak_terdengar = sum(int(x) for b in baris for x in re.findall(r"tidak terdengar ~(\d+)s", b["teks"]))

    skor = cakupan * yakin
    return {
        "detik_bicara": round(detik_bicara),
        "jumlah_kata": len(kata),
        "cakupan": round(cakupan, 3),
        "yakin": round(yakin, 3),
        "rata_prob": round(sum(p for _, _, p, _ in kata) / len(kata), 3),
        "detik_tidak_terdengar": tidak_terdengar,
        "skor": round(skor, 3),
        "nilai": next(n for batas, n in NILAI if skor >= batas),
    }


def ringkas(k):
    """Satu baris ringkasan untuk header transkrip."""
    if k["nilai"] in ("Kosong", "Tanpa ucapan"):
        return f"{k['nilai']} (tidak ada ucapan yang tertangkap)"
    return (
        f"{k['nilai']} (skor {k['skor']:.0%}) - {k['cakupan']:.0%} waktu bicara tertangkap, "
        f"{k['yakin']:.0%} kata yakin, {k['detik_tidak_terdengar']} detik tidak terdengar"
    )


# ---------------------------------------------------------------------- WER --
def normalisasi(teks):
    """Huruf kecil, buang tanda baca & penanda kita, supaya yang dibandingkan hanya katanya."""
    teks = re.sub(r"^\s*#.*$", " ", teks, flags=re.M)  # baris komentar/petunjuk
    teks = re.sub(r"^\s*\[\d\d:\d\d:\d\d\][^:]*:", " ", teks, flags=re.M)  # buang "[00:00:12] Pembicara 1:"
    teks = re.sub(r"\[tidak terdengar[^\]]*\]", " ", teks)
    teks = teks.replace("[tidak jelas:", " ").replace("(?)", "")
    teks = unicodedata.normalize("NFKC", teks.lower())
    teks = re.sub(r"[^\w\s-]", " ", teks)
    teks = teks.replace("-", " ")  # "kecil-kecil" vs "kecil kecil" dianggap sama
    return teks.split()


def jarak_edit(ref, hip):
    """Levenshtein per kata. Kembalikan (substitusi, hapus, sisip).

    Tabel d[i][j] = biaya minimum mengubah ref[:i] jadi hip[:j].
    """
    n, m = len(ref), len(hip)
    d = [[(0, 0, 0, 0)] * (m + 1) for _ in range(n + 1)]  # (total, sub, hapus, sisip)
    for i in range(1, n + 1):
        d[i][0] = (i, 0, i, 0)
    for j in range(1, m + 1):
        d[0][j] = (j, 0, 0, j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hip[j - 1]:
                d[i][j] = d[i - 1][j - 1]
                continue
            t, s, h, si = d[i - 1][j - 1]
            ganti = (t + 1, s + 1, h, si)
            t, s, h, si = d[i - 1][j]
            hapus = (t + 1, s, h + 1, si)
            t, s, h, si = d[i][j - 1]
            sisip = (t + 1, s, h, si + 1)
            d[i][j] = min(ganti, hapus, sisip)
    return d[n][m][1:]


def wer(teks_referensi, teks_hasil):
    ref, hip = normalisasi(teks_referensi), normalisasi(teks_hasil)
    if not ref:
        raise ValueError("Teks referensi kosong")
    sub, hapus, sisip = jarak_edit(ref, hip)
    w = (sub + hapus + sisip) / len(ref)
    return {
        "kata_referensi": len(ref),
        "kata_hasil": len(hip),
        "salah_ganti": sub,
        "hilang": hapus,
        "tambahan": sisip,
        "wer": round(w, 3),
        "akurasi": round(max(0.0, 1 - w), 3),
    }
