"""MEB'in resmî dizininden il ve ilçe müdürlüğü URL'lerini aktarır."""

from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from meb_kaynaklari import kaynak_ekle
from veritabani import tablo_olustur

DIZIN = "https://www.meb.gov.tr/baglantilar/mem/index_ilmem.php"
HEADERS = {"User-Agent": "Ihalex/1.0 (+resmi MEB kaynak kataloglama)"}


def _temiz(metin: str) -> str:
    return " ".join(metin.replace("\ufeff", "").split())


def _meb_origin(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if not host.endswith(".meb.gov.tr") or host == "www.meb.gov.tr":
        return None
    return f"https://{host}"


def aktar() -> dict[str, int]:
    tablo_olustur()
    oturum = requests.Session()
    oturum.headers.update(HEADERS)
    il_sayisi = 0
    ilce_sayisi = 0
    hatalar: list[dict[str, object]] = []

    # Merkezî dizindeki 81 il müdürlüğünün gerçek alan adlarını al.
    ana_yanit = oturum.get(DIZIN, timeout=(10, 30))
    ana_yanit.raise_for_status()
    ana_yanit.encoding = ana_yanit.apparent_encoding or "utf-8"
    ana_soup = BeautifulSoup(ana_yanit.text, "html.parser")
    for baglanti in ana_soup.select("a[href]"):
        metin = _temiz(baglanti.get_text(" ", strip=True))
        if "İl Mill" not in metin or "İlçe" in metin:
            continue
        origin = _meb_origin(baglanti.get("href", ""))
        if not origin:
            continue
        il_adi = metin.split(" İl Mill")[0]
        kaynak_ekle(
            metin, il_adi, "", origin + "/www/duyurular/kategori/2",
            aktif=True, dogrulandi=True, seviye="il", strateji="duyuru_listesi",
        )

    # Plaka kodları MEB dizinindeki ILKODU parametresidir.
    for il_kodu in range(1, 82):
        try:
            yanit = oturum.get(DIZIN, params={"ILKODU": il_kodu}, timeout=(10, 30))
            yanit.raise_for_status()
            yanit.encoding = yanit.apparent_encoding or "utf-8"
            soup = BeautifulSoup(yanit.text, "html.parser")
            baslik = soup.find(["h1", "h2"], string=re.compile("İl Mill", re.I))
            if not baslik:
                baslik = soup.find(["h1", "h2"])
            il_adi = _temiz(baslik.get_text(" ", strip=True)).split(" İl Mill")[0]
            if not il_adi:
                raise ValueError("İl adı bulunamadı")

            gorulen_hostlar: set[str] = set()
            for baglanti in soup.select("a[href]"):
                metin = _temiz(baglanti.get_text(" ", strip=True))
                if "İlçe Mill" not in metin:
                    continue
                origin = _meb_origin(baglanti.get("href", ""))
                if not origin or origin in gorulen_hostlar:
                    continue
                gorulen_hostlar.add(origin)
                ilce_adi = metin.split(" İlçe Mill")[0]
                kaynak_ekle(
                    metin, il_adi, ilce_adi,
                    origin + "/www/duyurular/kategori/2",
                    aktif=True, dogrulandi=True, seviye="ilce",
                    strateji="duyuru_listesi",
                )
                ilce_sayisi += 1

            il_sayisi += 1
            time.sleep(0.12)
        except Exception as hata:
            hatalar.append({"il_kodu": il_kodu, "hata": str(hata)})

    return {"il": il_sayisi, "ilce": ilce_sayisi, "hata": len(hatalar), "hatalar": hatalar}


if __name__ == "__main__":
    print(json.dumps(aktar(), ensure_ascii=False))
