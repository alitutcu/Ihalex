import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup


INDIRME_KLASORU = Path("ilanlar") / "meb_ekleri"

CIKTI_DOSYASI = "meb_icerik_sonucu.json"

DESTEKLENEN_UZANTILAR = {
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls"
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0.0.0 "
        "Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
}



def dosya_adi_temizle(dosya_adi):

    dosya_adi = unquote(
        dosya_adi
    )

    dosya_adi = dosya_adi.replace(
        "\\",
        "_"
    )

    dosya_adi = dosya_adi.replace(
        "/",
        "_"
    )

    dosya_adi = re.sub(
        r'[<>:"|?*]',
        "_",
        dosya_adi
    )

    dosya_adi = re.sub(
        r"\s+",
        "_",
        dosya_adi
    )

    return dosya_adi.strip(
        "._ "
    )



def url_dosya_adi_getir(url, sira):

    yol = urlparse(
        url
    ).path

    dosya_adi = os.path.basename(
        yol
    )

    dosya_adi = dosya_adi_temizle(
        dosya_adi
    )

    if not dosya_adi:

        dosya_adi = (
            f"ek_{sira}"
        )

    return dosya_adi



def uzanti_getir(url):

    yol = urlparse(
        url
    ).path

    uzanti = Path(
        yol
    ).suffix.lower()

    return uzanti



def tarih_bul(metin, etiket):

    desen = (
        rf"{re.escape(etiket)}"
        rf"\s*[:\-]?\s*"
        rf"(\d{{1,2}}\.\d{{1,2}}\.\d{{4}}"
        rf"(?:\s+\d{{1,2}}:\d{{2}})?)"
    )

    sonuc = re.search(
        desen,
        metin,
        re.IGNORECASE
    )

    if sonuc:

        return sonuc.group(
            1
        ).strip()

    return ""



def ihale_tarihi_bul(metin):

    desenler = [

        (
            r"(\d{1,2}[./]\d{1,2}[./]\d{4})"
            r"\s+tarihinde"
        ),

        (
            r"ihale\s+tarihi"
            r"\s*[:\-]?\s*"
            r"(\d{1,2}[./]\d{1,2}[./]\d{4})"
        ),

        (
            r"(\d{1,2}[./]\d{1,2}[./]\d{4})"
            r"\s+günü"
        )

    ]

    for desen in desenler:

        sonuc = re.search(
            desen,
            metin,
            re.IGNORECASE
        )

        if sonuc:

            return sonuc.group(
                1
            ).replace(
                "/",
                "."
            )

    return ""



def sayfa_getir(url):

    try:

        cevap = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        cevap.raise_for_status()

        cevap.encoding = (
            cevap.apparent_encoding
            or "utf-8"
        )

        return cevap


    except requests.RequestException as hata:

        print()
        print(
            "Sayfa bağlantı hatası:"
        )

        print(hata)

        return None



def baslik_bul(soup):

    h1 = soup.find(
        "h1"
    )

    if h1:

        metin = h1.get_text(
            " ",
            strip=True
        )

        if metin:

            return metin


    h2 = soup.find(
        "h2"
    )

    if h2:

        metin = h2.get_text(
            " ",
            strip=True
        )

        if metin:

            return metin


    if soup.title:

        return soup.title.get_text(
            " ",
            strip=True
        )


    return ""



def ana_metin_bul(soup):

    seciciler = [

        "article",

        ".content",

        ".icerik",

        ".haberDetay",

        ".haber-detay",

        ".icerikDetay",

        ".detail",

        ".page-content",

        "main"

    ]


    adaylar = []


    for secici in seciciler:

        for alan in soup.select(
            secici
        ):

            metin = alan.get_text(
                "\n",
                strip=True
            )

            if metin:

                adaylar.append(
                    metin
                )


    if adaylar:

        adaylar.sort(
            key=len,
            reverse=True
        )

        return adaylar[0]


    body = soup.find(
        "body"
    )

    if body:

        return body.get_text(
            "\n",
            strip=True
        )


    return ""



def ek_dosyalari_bul(soup, ana_url):

    ekler = []

    gorulen_url = set()


    for baglanti in soup.find_all(
        "a",
        href=True
    ):

        href = baglanti.get(
            "href",
            ""
        ).strip()

        if not href:

            continue


        tam_url = urljoin(
            ana_url,
            href
        )


        uzanti = uzanti_getir(
            tam_url
        )


        meb_dosya_mi = (
            "meb_iys_dosyalar"
            in tam_url.lower()
        )


        desteklenen_mi = (
            uzanti
            in DESTEKLENEN_UZANTILAR
        )


        if not (
            meb_dosya_mi
            or
            desteklenen_mi
        ):

            continue


        if tam_url in gorulen_url:

            continue


        gorulen_url.add(
            tam_url
        )


        baglanti_metni = (
            baglanti.get_text(
                " ",
                strip=True
            )
            or
            "Ek dosya"
        )


        ekler.append(
            {
                "baslik": baglanti_metni,
                "url": tam_url,
                "uzanti": uzanti,
                "indirildi": False,
                "yerel_dosya": "",
                "hata": ""
            }
        )


    return ekler



def dosya_indir(ek, sira):

    INDIRME_KLASORU.mkdir(
        parents=True,
        exist_ok=True
    )


    dosya_adi = url_dosya_adi_getir(
        ek["url"],
        sira
    )


    uzanti = ek.get(
        "uzanti",
        ""
    )


    if not Path(
        dosya_adi
    ).suffix and uzanti:

        dosya_adi += uzanti


    hedef = (
        INDIRME_KLASORU
        /
        dosya_adi
    )


    try:

        cevap = requests.get(
            ek["url"],
            headers=HEADERS,
            timeout=60,
            stream=True
        )

        cevap.raise_for_status()


        with open(
            hedef,
            "wb"
        ) as dosya:

            for parca in cevap.iter_content(
                chunk_size=8192
            ):

                if parca:

                    dosya.write(
                        parca
                    )


        ek["indirildi"] = True

        ek["yerel_dosya"] = str(
            hedef
        )

        return True


    except requests.RequestException as hata:

        ek["hata"] = str(
            hata
        )

        return False



def meb_icerik_oku(url):

    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("MEB İÇERİK OKUYUCU")
    print("==============================")

    print()
    print(
        "Sayfa:"
    )

    print(url)


    cevap = sayfa_getir(
        url
    )


    if cevap is None:

        return None


    soup = BeautifulSoup(
        cevap.text,
        "html.parser"
    )


    baslik = baslik_bul(
        soup
    )


    ana_metin = ana_metin_bul(
        soup
    )


    ekler = ek_dosyalari_bul(
        soup,
        url
    )


    yayin_tarihi = tarih_bul(
        ana_metin,
        "Yayın"
    )


    guncelleme_tarihi = tarih_bul(
        ana_metin,
        "Güncelleme"
    )


    ihale_tarihi = ihale_tarihi_bul(
        ana_metin
    )


    sonuc = {

        "kaynak": "MEB",

        "sayfa_url": url,

        "sayfa_basligi": baslik,

        "icerik": ana_metin,

        "yayin_tarihi": yayin_tarihi,

        "guncelleme_tarihi":
            guncelleme_tarihi,

        "ihale_tarihi":
            ihale_tarihi,

        "ek_dosyalar": ekler,

        "ek_sayisi": len(
            ekler
        ),

        "okuma_tarihi":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    }


    print()
    print(
        "Başlık:",
        baslik
    )

    print(
        "Yayın tarihi:",
        yayin_tarihi
        or "Bulunamadı"
    )

    print(
        "Güncelleme tarihi:",
        guncelleme_tarihi
        or "Bulunamadı"
    )

    print(
        "İhale tarihi:",
        ihale_tarihi
        or "Bulunamadı"
    )

    print(
        "Ek dosya sayısı:",
        len(
            ekler
        )
    )


    for sira, ek in enumerate(
        ekler,
        start=1
    ):

        print()
        print(
            f"{sira}. ek:"
        )

        print(
            "Başlık:",
            ek["baslik"]
        )

        print(
            "Tür:",
            ek["uzanti"]
            or "bilinmiyor"
        )

        print(
            "URL:",
            ek["url"]
        )


        basarili = dosya_indir(
            ek,
            sira
        )


        if basarili:

            print(
                "İndirildi:",
                ek["yerel_dosya"]
            )

        else:

            print(
                "İndirme hatası:",
                ek["hata"]
            )


    with open(
        CIKTI_DOSYASI,
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            sonuc,
            dosya,
            ensure_ascii=False,
            indent=4
        )


    print()
    print("==============================")
    print("MEB İÇERİĞİ OKUNDU")
    print("==============================")

    print(
        "JSON çıktısı:",
        CIKTI_DOSYASI
    )

    print(
        "Ek klasörü:",
        INDIRME_KLASORU
    )


    return sonuc



if __name__ == "__main__":

    TEST_URL = (
        "https://mamak.meb.gov.tr/"
        "www/kantin-ihalesi/icerik/2619"
    )

    meb_icerik_oku(
        TEST_URL
    )