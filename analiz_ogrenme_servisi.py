"""Manuel doğrulamaları güvenli ve açıklanabilir öğrenme örneklerine dönüştürür."""

from __future__ import annotations

from hashlib import sha256
import json
import re
import unicodedata
from typing import Mapping


ZORUNLU_ALANLAR = (
    "il",
    "ilce",
    "okul_adi",
    "okul_turu",
    "ogrenci_sayisi",
    "muhammen_bedel_aylik",
)
_DURAK_KELIMELER = {
    "ait", "bagli", "bakanligina", "bulunan", "egitim", "hazine", "ilce",
    "maliye", "milli", "mudurlugune", "mudurlugu", "okulu", "tc",
}


def _anahtar(deger: object) -> str:
    metin = unicodedata.normalize("NFKD", str(deger or "").casefold()).replace("ı", "i")
    metin = "".join(harf for harf in metin if not unicodedata.combining(harf))
    return " ".join(re.findall(r"[a-z0-9]+", metin))


def _esit(sol: object, sag: object) -> bool:
    if sol is None and sag is None:
        return True
    try:
        return abs(float(sol) - float(sag)) < 0.000001
    except (TypeError, ValueError):
        return _anahtar(sol) == _anahtar(sag)


def ogrenme_ornegi_kaydet(
    conn: object,
    aday_id: int,
    dogrulanmis: Mapping[str, object],
    *,
    duzelten: str,
    olusturma_tarihi: str,
) -> int:
    """Belge ile manuel doğrulama farkını gelecekte kullanılacak örnek olarak saklar."""
    satir = conn.execute("""
        SELECT d.kaynak_id, a.kaynak_belge_id, k.il,
               COALESCE(k.ilce, '') AS ilce, a.okul_adi, a.okul_turu,
               a.ogrenci_sayisi, a.muhammen_bedel_aylik, a.ham_metin
        FROM duyuru_adaylari d
        JOIN kaynaklar k ON k.id=d.kaynak_id
        LEFT JOIN ilan_analiz_verileri a ON a.aday_id=d.id
        WHERE d.id=?
    """, (int(aday_id),)).fetchone()
    if satir is None:
        return 0

    belge = {alan: satir[alan] for alan in ZORUNLU_ALANLAR}
    dogru = {alan: dogrulanmis.get(alan) for alan in ZORUNLU_ALANLAR}
    degisen = [alan for alan in ZORUNLU_ALANLAR if not _esit(belge[alan], dogru[alan])]
    ham_metin = str(satir["ham_metin"] or "")
    parmak_izi = sha256(ham_metin.encode("utf-8")).hexdigest() if ham_metin else None
    cursor = conn.execute("""
        INSERT INTO analiz_ogrenme_ornekleri(
            aday_id, kaynak_id, belge_id, belge_degerleri_json,
            dogrulanmis_degerler_json, degisen_alanlar_json,
            metin_parmak_izi, duzelten, olusturma_tarihi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(aday_id), int(satir["kaynak_id"]), satir["kaynak_belge_id"],
        json.dumps(belge, ensure_ascii=False),
        json.dumps(dogru, ensure_ascii=False),
        json.dumps(degisen, ensure_ascii=False),
        parmak_izi, str(duzelten or "admin")[:80], olusturma_tarihi,
    ))
    return int(cursor.lastrowid)


def ogrenilmis_okul_bilgisini_uygula(
    conn: object,
    aday_id: int,
    veri: Mapping[str, object],
) -> dict[str, object]:
    """Yalnız yüksek güvenli okul kimliği/türü eşleşmesini yeni belgeye uygular."""
    sonuc = dict(veri)
    if sonuc.get("okul_adi") and sonuc.get("okul_turu"):
        return sonuc
    aday = conn.execute("""
        SELECT d.kaynak_id, d.baslik, k.il, COALESCE(k.ilce, '') AS ilce
        FROM duyuru_adaylari d
        JOIN kaynaklar k ON k.id=d.kaynak_id
        WHERE d.id=?
    """, (int(aday_id),)).fetchone()
    if aday is None:
        return sonuc

    belge_anahtari = _anahtar(
        f"{aday['baslik']} {str(sonuc.get('ham_metin') or '')[:100000]}"
    )
    mevcut_okul = _anahtar(sonuc.get("okul_adi"))
    ornekler = conn.execute("""
        SELECT e.id, e.dogrulanmis_degerler_json
        FROM analiz_ogrenme_ornekleri e
        JOIN duyuru_adaylari d ON d.id=e.aday_id
        JOIN kaynaklar k ON k.id=d.kaynak_id
        WHERE e.kaynak_id=?
           OR (k.il=? AND COALESCE(k.ilce, '')=?)
        ORDER BY e.olusturma_tarihi DESC, e.id DESC
        LIMIT 100
    """, (int(aday["kaynak_id"]), aday["il"], aday["ilce"])).fetchall()
    for ornek in ornekler:
        try:
            dogru = json.loads(str(ornek["dogrulanmis_degerler_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        okul_adi = str(dogru.get("okul_adi") or "").strip()
        okul_anahtari = _anahtar(okul_adi)
        anlamli = [
            kelime for kelime in okul_anahtari.split()
            if len(kelime) >= 3 and kelime not in _DURAK_KELIMELER
        ]
        isim_eslesti = bool(
            okul_anahtari
            and (
                okul_anahtari in belge_anahtari
                or (mevcut_okul and (
                    mevcut_okul in okul_anahtari or okul_anahtari in mevcut_okul
                ))
                or (len(anlamli) >= 2 and all(k in belge_anahtari for k in anlamli))
            )
        )
        if not isim_eslesti:
            continue
        if not sonuc.get("okul_adi"):
            sonuc["okul_adi"] = okul_adi
        if not sonuc.get("okul_turu") and dogru.get("okul_turu"):
            sonuc["okul_turu"] = dogru["okul_turu"]
        conn.execute(
            "UPDATE analiz_ogrenme_ornekleri "
            "SET uygulanma_sayisi=uygulanma_sayisi+1 WHERE id=?",
            (int(ornek["id"]),),
        )
        break
    return sonuc
