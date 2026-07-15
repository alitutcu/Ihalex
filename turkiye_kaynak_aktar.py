"""81 il ve ilçeleri İhalex MEB kaynak kataloğuna aktarır."""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from contextlib import closing
from pathlib import Path

from meb_kaynaklari import kaynak_ekle
from veritabani import baglan, tablo_olustur

KOK = Path(__file__).resolve().parent
ILCE_DOSYASI = KOK / "veri" / "turkiye_ilceler.json"

IL_HOSTLARI = {
    "Afyonkarahisar": "afyon", "Kahramanmaraş": "kahramanmaras",
    "Şanlıurfa": "sanliurfa",
}

OZEL_KAYNAKLAR = (
    ("İstanbul İl Millî Eğitim Müdürlüğü", "İstanbul", "",
     "https://istanbul.meb.gov.tr/www/ihale-dosyalari/dosya/9", "il", "toplu_dosya"),
    ("Mamak İlçe Millî Eğitim Müdürlüğü", "Ankara", "Mamak",
     "https://mamak.meb.gov.tr/www/duyurular/kategori/2", "ilce", "duyuru_listesi"),
    ("İzmir İl Millî Eğitim Müdürlüğü", "İzmir", "",
     "https://izmir.meb.gov.tr/www/ihale-ilanlari/icerik/2229", "il", "toplu_dosya"),
    ("Kadıköy İlçe Millî Eğitim Müdürlüğü", "İstanbul", "Kadıköy",
     "https://kadikoy.meb.gov.tr/www/duyurular/kategori/2", "ilce", "duyuru_listesi"),
    ("Malatya İl Millî Eğitim Müdürlüğü", "Malatya", "",
     "https://malatya.meb.gov.tr/www/duyurular/kategori/2", "il", "duyuru_listesi"),
    ("Zonguldak İl Millî Eğitim Müdürlüğü", "Zonguldak", "",
     "https://zonguldak.meb.gov.tr/www/duyurular/kategori/2", "il", "duyuru_listesi"),
)


def metin_duzelt(metin: str) -> str:
    """Eski cp1254 verisinin Latin-1 olarak okunmuş karakterlerini düzeltir."""
    try:
        return metin.encode("latin1").decode("cp1254")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return metin


def host_adi(metin: str) -> str:
    ceviri = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    sade = unicodedata.normalize("NFKD", metin.translate(ceviri))
    return "".join(harf for harf in sade.lower() if harf.isalnum())


def aktar() -> dict[str, int]:
    tablo_olustur()
    ham = json.loads(ILCE_DOSYASI.read_text(encoding="utf-8"))
    veri = {metin_duzelt(il): [metin_duzelt(x) for x in ilceler]
            for il, ilceler in ham.items()}

    with closing(baglan()) as conn, conn:
        for il, ilceler in veri.items():
            conn.execute("INSERT OR IGNORE INTO bolgeler(il, ilce, tur) VALUES (?, '', 'il')", (il,))
            conn.executemany(
                "INSERT OR IGNORE INTO bolgeler(il, ilce, tur) VALUES (?, ?, 'ilce')",
                ((il, ilce) for ilce in ilceler),
            )

    # 81 il için standart duyuru adresleri aday olarak eklenir.
    for il in veri:
        host = IL_HOSTLARI.get(il, host_adi(il))
        kaynak_ekle(
            f"{il} İl Millî Eğitim Müdürlüğü", il, "",
            f"https://{host}.meb.gov.tr/www/duyurular/kategori/2",
            aktif=False, dogrulandi=False, seviye="il", strateji="duyuru_listesi",
        )

    # Aynı isimli ilçelerde host tahmini güvenilir olmadığından doğrulama kuyruğuna alınmaz.
    sayac = Counter(host_adi(ilce) for ilceler in veri.values() for ilce in ilceler if ilce != "Merkez")
    ilce_adayi = 0
    for il, ilceler in veri.items():
        for ilce in ilceler:
            slug = host_adi(ilce)
            if ilce == "Merkez" or sayac[slug] != 1:
                continue
            kaynak_ekle(
                f"{ilce} İlçe Millî Eğitim Müdürlüğü", il, ilce,
                f"https://{slug}.meb.gov.tr/www/duyurular/kategori/2",
                aktif=False, dogrulandi=False, seviye="ilce", strateji="duyuru_listesi",
            )
            ilce_adayi += 1

    for kurum, il, ilce, url, seviye, strateji in OZEL_KAYNAKLAR:
        kaynak_ekle(kurum, il, ilce, url, aktif=True, dogrulandi=True,
                    seviye=seviye, strateji=strateji)

    return {"il": len(veri), "ilce": sum(map(len, veri.values())), "ilce_adayi": ilce_adayi}


if __name__ == "__main__":
    sonuc = aktar()
    print(json.dumps(sonuc, ensure_ascii=False))
