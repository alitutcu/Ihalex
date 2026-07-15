import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from playwright.sync_api import sync_playwright


CIKTI_DOSYASI = "meb_liste_sonucu.json"
HATA_EKRANI = "meb_liste_hata.png"
SAYFA_EKRANI = "meb_liste_sayfasi.png"
HTML_DOSYASI = "meb_liste_rendered.html"

DESTEKLENEN_UZANTILAR = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx"
}

KANTIN_KELIMELERI = [
    "kantin",
    "okul kantini",
    "kantin ihalesi",
    "kantin kiralama",
    "kantin işletme",
    "büfe",
    "bufe",
    "çay ocağı",
    "cay ocagi",
    "kafeterya"
]


def turkce_normalize(metin):

    if not metin:
        return ""

    ceviri = str.maketrans(
        {
            "ç": "c",
            "Ç": "c",
            "ğ": "g",
            "Ğ": "g",
            "ı": "i",
            "İ": "i",
            "ö": "o",
            "Ö": "o",
            "ş": "s",
            "Ş": "s",
            "ü": "u",
            "Ü": "u"
        }
    )

    return (
        str(metin)
        .translate(ceviri)
        .lower()
        .strip()
    )


def uzanti_getir(url):

    try:

        yol = urlparse(
            url
        ).path

        return Path(
            yol
        ).suffix.lower()

    except Exception:

        return ""


def dosya_adi_getir(url):

    try:

        yol = urlparse(
            url
        ).path

        dosya_adi = os.path.basename(
            yol
        )

        return unquote(
            dosya_adi
        )

    except Exception:

        return ""


def kantin_ilgili_mi(metin):

    normal_metin = turkce_normalize(
        metin
    )

    return any(
        turkce_normalize(
            kelime
        ) in normal_metin
        for kelime in KANTIN_KELIMELERI
    )


def tarih_bul(metin):

    sonuc = re.search(
        r"\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b",
        metin or ""
    )

    if not sonuc:
        return ""

    return sonuc.group(
        1
    ).replace(
        "/",
        "."
    )


def boyut_bul(metin):

    sonuc = re.search(
        (
            r"\b"
            r"(\d+(?:[.,]\d+)?)"
            r"\s*(KB|MB|GB)\b"
        ),
        metin or "",
        re.IGNORECASE
    )

    if not sonuc:
        return ""

    return (
        sonuc.group(1)
        + " "
        + sonuc.group(2).upper()
    )


def temiz_baslik_olustur(
        baglanti_metni,
        satir_metni,
        dosya_adi
):

    for aday in [
        satir_metni,
        baglanti_metni,
        dosya_adi
    ]:

        if not aday:
            continue

        temiz = re.sub(
            r"\s+",
            " ",
            aday
        ).strip()

        temiz = re.sub(
            r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b",
            "",
            temiz
        )

        temiz = re.sub(
            (
                r"\b\d+(?:[.,]\d+)?"
                r"\s*(?:KB|MB|GB)\b"
            ),
            "",
            temiz,
            flags=re.IGNORECASE
        )

        temiz = re.sub(
            r"\s+",
            " ",
            temiz
        ).strip(
            " |-"
        )

        if len(
            temiz
        ) >= 3:

            return temiz

    return dosya_adi or "İhale dosyası"


def rendered_html_baglantilarini_al(html):

    desenler = [
        (
            r"""["']"""
            r"""([^"']*"""
            r"""meb_iys_dosyalar"""
            r"""[^"']*\.(?:pdf|docx?|xlsx?))"""
            r"""["']"""
        ),
        (
            r"""["']"""
            r"""([^"']+\.(?:pdf|docx?|xlsx?))"""
            r"""["']"""
        )
    ]

    bulunanlar = []
    gorulen = set()

    for desen in desenler:

        for adres in re.findall(
            desen,
            html,
            re.IGNORECASE
        ):

            adres = (
                adres
                .replace(
                    "\\/",
                    "/"
                )
                .replace(
                    "&amp;",
                    "&"
                )
            )

            if adres in gorulen:
                continue

            gorulen.add(
                adres
            )

            bulunanlar.append(
                {
                    "href": adres,
                    "metin": "",
                    "satir_metni": "",
                    "yontem": "rendered_html"
                }
            )

    return bulunanlar


def dom_baglantilarini_al(page):

    return page.locator(
        "a, [data-url], [data-href], "
        "[data-file], [data-download]"
    ).evaluate_all(
        """
        (elements) => {
            const sonuc = [];

            for (const element of elements) {
                const row =
                    element.closest("tr")
                    || element.closest("li")
                    || element.closest(".row")
                    || element.closest(".card")
                    || element.parentElement;

                const metin =
                    (element.innerText
                    || element.textContent
                    || "").trim();

                const satirMetni =
                    row
                    ? (
                        row.innerText
                        || row.textContent
                        || ""
                    ).trim()
                    : "";

                const degerler = [
                    {
                        alan: "href",
                        deger:
                            element.href
                            || element.getAttribute("href")
                    },
                    {
                        alan: "data-url",
                        deger:
                            element.getAttribute("data-url")
                    },
                    {
                        alan: "data-href",
                        deger:
                            element.getAttribute("data-href")
                    },
                    {
                        alan: "data-file",
                        deger:
                            element.getAttribute("data-file")
                    },
                    {
                        alan: "data-download",
                        deger:
                            element.getAttribute("data-download")
                    }
                ];

                for (const kayit of degerler) {
                    if (!kayit.deger) {
                        continue;
                    }

                    sonuc.push({
                        href: kayit.deger,
                        metin: metin,
                        satir_metni: satirMetni,
                        yontem: kayit.alan
                    });
                }
            }

            return sonuc;
        }
        """
    )


def kayitlari_temizle(
        ham_baglantilar,
        ana_url
):

    sonuclar = []
    gorulen_url = set()

    for ham in ham_baglantilar:

        href = str(
            ham.get(
                "href",
                ""
            )
            or ""
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

        if (
            uzanti not in DESTEKLENEN_UZANTILAR
            and
            "meb_iys_dosyalar"
            not in tam_url.lower()
        ):
            continue

        if tam_url in gorulen_url:
            continue

        gorulen_url.add(
            tam_url
        )

        baglanti_metni = str(
            ham.get(
                "metin",
                ""
            )
            or ""
        ).strip()

        satir_metni = str(
            ham.get(
                "satir_metni",
                ""
            )
            or ""
        ).strip()

        dosya_adi = dosya_adi_getir(
            tam_url
        )

        baslik = temiz_baslik_olustur(
            baglanti_metni,
            satir_metni,
            dosya_adi
        )

        birlesik_metin = " ".join(
            [
                baslik,
                baglanti_metni,
                satir_metni,
                dosya_adi
            ]
        )

        sonuclar.append(
            {
                "baslik": baslik,
                "dosya_adi": dosya_adi,
                "url": tam_url,
                "uzanti": uzanti,
                "tarih": tarih_bul(
                    birlesik_metin
                ),
                "boyut": boyut_bul(
                    birlesik_metin
                ),
                "kantin_ilgili": kantin_ilgili_mi(
                    birlesik_metin
                ),
                "satir_metni": satir_metni,
                "bulunma_yontemi": ham.get(
                    "yontem",
                    ""
                )
            }
        )

    return sonuclar


def sayfaya_git(
        page,
        hedef_url
):

    domain = urlparse(
        hedef_url
    ).netloc

    ana_sayfa = (
        "https://"
        + domain
        + "/"
    )

    denemeler = [
        ana_sayfa,
        hedef_url,
        hedef_url
    ]

    son_hata = None

    for sira, adres in enumerate(
        denemeler,
        start=1
    ):

        print()
        print(
            f"Bağlantı denemesi {sira}:"
        )

        print(
            adres
        )

        try:

            page.goto(
                adres,
                wait_until="commit",
                timeout=60000
            )

            page.wait_for_timeout(
                3000
            )

            if adres == ana_sayfa:

                continue

            try:

                page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=30000
                )

            except Exception:

                pass

            try:

                page.wait_for_load_state(
                    "networkidle",
                    timeout=15000
                )

            except Exception:

                pass

            page.wait_for_timeout(
                7000
            )

            return True

        except Exception as hata:

            son_hata = hata

            print(
                "Deneme başarısız:"
            )

            print(hata)

            page.wait_for_timeout(
                3000
            )

    print()
    print(
        "Tüm bağlantı denemeleri başarısız."
    )

    if son_hata:

        print(
            son_hata
        )

    return False


def meb_liste_tara(url):

    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("MEB İHALE LİSTE TARAYICI V3")
    print("==============================")

    print()
    print(
        "Liste URL:"
    )

    print(url)

    ham_baglantilar = []
    aktif_url = url
    sayfa_basligi = ""

    with sync_playwright() as p:

        browser = None

        try:

            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-http2",
                    "--disable-quic",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
            )

            context = browser.new_context(
                viewport={
                    "width": 1366,
                    "height": 900
                },
                locale="tr-TR",
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/130.0.0.0 "
                    "Safari/537.36"
                ),
                extra_http_headers={
                    "Accept-Language":
                        "tr-TR,tr;q=0.9,en;q=0.8"
                }
            )

            page = context.new_page()

            basarili = sayfaya_git(
                page,
                url
            )

            if not basarili:

                try:

                    page.screenshot(
                        path=HATA_EKRANI,
                        full_page=True
                    )

                except Exception:

                    pass

                return None

            aktif_url = page.url
            sayfa_basligi = page.title()

            print()
            print(
                "Sayfa başlığı:",
                sayfa_basligi
            )

            print(
                "Aktif URL:",
                aktif_url
            )

            body_metni = page.locator(
                "body"
            ).inner_text()

            print(
                "Sayfa metni:",
                len(
                    body_metni
                ),
                "karakter"
            )

            dom_baglantilari = (
                dom_baglantilarini_al(
                    page
                )
            )

            html = page.content()

            html_baglantilari = (
                rendered_html_baglantilarini_al(
                    html
                )
            )

            ham_baglantilar.extend(
                dom_baglantilari
            )

            ham_baglantilar.extend(
                html_baglantilari
            )

            print(
                "DOM bağlantısı:",
                len(
                    dom_baglantilari
                )
            )

            print(
                "HTML dosya bağlantısı:",
                len(
                    html_baglantilari
                )
            )

            with open(
                HTML_DOSYASI,
                "w",
                encoding="utf-8"
            ) as dosya:

                dosya.write(
                    html
                )

            page.screenshot(
                path=SAYFA_EKRANI,
                full_page=True
            )

        except Exception as hata:

            print()
            print(
                "PLAYWRIGHT HATASI:"
            )

            print(hata)

            return None

        finally:

            if browser:

                browser.close()

    dosyalar = kayitlari_temizle(
        ham_baglantilar,
        aktif_url
    )

    kantin_dosyalari = [
        dosya
        for dosya in dosyalar
        if dosya.get(
            "kantin_ilgili",
            False
        )
    ]

    sonuc = {
        "kaynak": "MEB",
        "sayfa_url": url,
        "aktif_url": aktif_url,
        "sayfa_basligi": sayfa_basligi,
        "sayfa_turu": "liste",
        "toplam_dosya": len(
            dosyalar
        ),
        "kantin_dosya_sayisi": len(
            kantin_dosyalari
        ),
        "dosyalar": dosyalar,
        "kantin_dosyalari": kantin_dosyalari,
        "tarama_tarihi": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

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
    print("MEB LİSTE TARAMASI TAMAMLANDI")
    print("==============================")

    print(
        "Toplam dosya:",
        len(
            dosyalar
        )
    )

    print(
        "Kantinle ilgili dosya:",
        len(
            kantin_dosyalari
        )
    )

    for sira, dosya in enumerate(
        kantin_dosyalari,
        start=1
    ):

        print()
        print(
            f"{sira})",
            dosya["baslik"]
        )

        print(
            "Tarih:",
            dosya.get(
                "tarih",
                ""
            )
            or "Bulunamadı"
        )

        print(
            "URL:",
            dosya["url"]
        )

    print()
    print(
        "JSON çıktısı:",
        CIKTI_DOSYASI
    )

    print(
        "HTML çıktısı:",
        HTML_DOSYASI
    )

    print(
        "Ekran görüntüsü:",
        SAYFA_EKRANI
    )

    return sonuc


def main():

    print()
    print(
        "MEB ihale liste sayfası linkini gir:"
    )

    url = input(
        "> "
    ).strip()

    if not url:

        print(
            "URL girilmedi."
        )

        return

    meb_liste_tara(
        url
    )


if __name__ == "__main__":

    main()