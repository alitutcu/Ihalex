import json
import os
from datetime import datetime
from urllib.parse import urlparse

from meb_ihale_aktar import meb_ihale_aktar


LINK_DOSYASI = "ihale_linkleri.json"


def bos_veri_olustur():

    return {
        "linkler": []
    }



def veri_yukle():

    if not os.path.exists(
        LINK_DOSYASI
    ):

        veri = bos_veri_olustur()

        veri_kaydet(
            veri
        )

        return veri


    try:

        with open(
            LINK_DOSYASI,
            "r",
            encoding="utf-8"
        ) as dosya:

            veri = json.load(
                dosya
            )


    except json.JSONDecodeError:

        print()
        print(
            "HATA: ihale_linkleri.json "
            "bozuk JSON formatında."
        )

        return None


    except Exception as hata:

        print()
        print(
            "Link dosyası okuma hatası:"
        )

        print(hata)

        return None


    if "linkler" not in veri:

        veri["linkler"] = []


    return veri



def veri_kaydet(veri):

    with open(
        LINK_DOSYASI,
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            veri,
            dosya,
            ensure_ascii=False,
            indent=4
        )



def url_gecerli_mi(url):

    if not url:

        return False


    try:

        adres = urlparse(
            url
        )


        if adres.scheme not in {
            "http",
            "https"
        }:

            return False


        if not adres.netloc:

            return False


        return True


    except Exception:

        return False



def kaynak_turu_belirle(url):

    domain = urlparse(
        url
    ).netloc.lower()


    if (
        domain.endswith(
            ".meb.gov.tr"
        )
        or
        domain == "meb.gov.tr"
    ):

        return "meb"


    return "diger"



def link_var_mi(veri, url):

    temiz_url = url.strip().rstrip(
        "/"
    )


    for kayit in veri.get(
        "linkler",
        []
    ):

        mevcut_url = (
            kayit.get(
                "url",
                ""
            )
            .strip()
            .rstrip(
                "/"
            )
        )


        if mevcut_url == temiz_url:

            return True


    return False



def link_ekle():

    veri = veri_yukle()


    if veri is None:

        return


    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("İHALE LİNKİ EKLE")
    print("==============================")


    url = input(
        "İhale linki: "
    ).strip()


    if not url_gecerli_mi(
        url
    ):

        print()
        print(
            "HATA: Geçerli bir internet "
            "adresi girmedin."
        )

        return


    if link_var_mi(
        veri,
        url
    ):

        print()
        print(
            "Bu bağlantı zaten kayıtlı."
        )

        return


    il = input(
        "İl: "
    ).strip()


    ilce = input(
        "İlçe: "
    ).strip()


    kurum = input(
        "Kurum/Kaynak adı: "
    ).strip()


    not_metni = input(
        "Not: "
    ).strip()


    kaynak_turu = kaynak_turu_belirle(
        url
    )


    yeni_kayit = {

        "id":
            sonraki_id_bul(
                veri
            ),

        "url":
            url,

        "il":
            il,

        "ilce":
            ilce,

        "kurum":
            kurum,

        "kaynak_turu":
            kaynak_turu,

        "durum":
            "bekliyor",

        "aktif":
            True,

        "deneme_sayisi":
            0,

        "son_hata":
            "",

        "not":
            not_metni,

        "eklenme_tarihi":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "son_islem_tarihi":
            "",

        "basarili_islem_tarihi":
            ""

    }


    veri["linkler"].append(
        yeni_kayit
    )


    veri_kaydet(
        veri
    )


    print()
    print("==============================")
    print("İHALE LİNKİ EKLENDİ")
    print("==============================")

    print(
        "ID:",
        yeni_kayit["id"]
    )

    print(
        "Kaynak türü:",
        kaynak_turu
    )

    print(
        "Durum:",
        yeni_kayit["durum"]
    )



def sonraki_id_bul(veri):

    idler = []


    for kayit in veri.get(
        "linkler",
        []
    ):

        try:

            idler.append(
                int(
                    kayit.get(
                        "id",
                        0
                    )
                )
            )

        except (
            TypeError,
            ValueError
        ):

            continue


    if not idler:

        return 1


    return max(
        idler
    ) + 1



def linkleri_listele():

    veri = veri_yukle()


    if veri is None:

        return


    linkler = veri.get(
        "linkler",
        []
    )


    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("İHALE LİNKLERİ")
    print("==============================")


    if not linkler:

        print(
            "Henüz ihale bağlantısı yok."
        )

        return


    for kayit in linkler:

        aktif_metni = (
            "AKTİF"
            if kayit.get(
                "aktif",
                True
            )
            else "PASİF"
        )


        print()
        print("------------------------------")

        print(
            "ID:",
            kayit.get(
                "id"
            )
        )

        print(
            "Konum:",
            kayit.get(
                "il",
                ""
            ),
            "/",
            kayit.get(
                "ilce",
                ""
            )
        )

        print(
            "Kurum:",
            kayit.get(
                "kurum",
                ""
            )
        )

        print(
            "Kaynak türü:",
            kayit.get(
                "kaynak_turu",
                ""
            )
        )

        print(
            "Durum:",
            kayit.get(
                "durum",
                ""
            )
        )

        print(
            "Aktiflik:",
            aktif_metni
        )

        print(
            "Deneme:",
            kayit.get(
                "deneme_sayisi",
                0
            )
        )

        print(
            "URL:"
        )

        print(
            kayit.get(
                "url",
                ""
            )
        )


        if kayit.get(
            "son_hata"
        ):

            print(
                "Son hata:",
                kayit["son_hata"]
            )


        if kayit.get(
            "not"
        ):

            print(
                "Not:",
                kayit["not"]
            )


    print()
    print("==============================")

    print(
        "Toplam link:",
        len(
            linkler
        )
    )



def tek_link_isle(kayit):

    url = kayit.get(
        "url",
        ""
    )


    kaynak_turu = kayit.get(
        "kaynak_turu",
        ""
    )


    print()
    print("==============================")

    print(
        "İşleniyor - ID:",
        kayit.get(
            "id"
        )
    )

    print(
        url
    )

    print("==============================")


    kayit["deneme_sayisi"] = (
        int(
            kayit.get(
                "deneme_sayisi",
                0
            )
        )
        + 1
    )


    kayit["son_islem_tarihi"] = (
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )


    if kaynak_turu != "meb":

        kayit["durum"] = (
            "desteklenmiyor"
        )

        kayit["son_hata"] = (
            "Bu kaynak türü için "
            "okuyucu henüz hazırlanmadı."
        )

        print(
            kayit["son_hata"]
        )

        return False


    try:

        basarili = meb_ihale_aktar(
            url
        )


        if basarili:

            kayit["durum"] = (
                "tamamlandi"
            )

            kayit["son_hata"] = ""

            kayit[
                "basarili_islem_tarihi"
            ] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            print()
            print(
                "Link başarıyla işlendi."
            )

            return True


        kayit["durum"] = (
            "hata"
        )

        kayit["son_hata"] = (
            "Aktarım motoru işlemi "
            "tamamlayamadı."
        )

        return False


    except Exception as hata:

        kayit["durum"] = (
            "hata"
        )

        kayit["son_hata"] = str(
            hata
        )

        print()
        print(
            "Link işleme hatası:"
        )

        print(hata)

        return False



def bekleyen_linkleri_isle():

    veri = veri_yukle()


    if veri is None:

        return


    bekleyenler = []


    for kayit in veri.get(
        "linkler",
        []
    ):

        if not kayit.get(
            "aktif",
            True
        ):

            continue


        if kayit.get(
            "durum"
        ) in {
            "bekliyor",
            "hata"
        }:

            bekleyenler.append(
                kayit
            )


    print()
    print("==============================")
    print("KANTİN RADAR AI")
    print("BEKLEYEN İHALELER İŞLENİYOR")
    print("==============================")


    if not bekleyenler:

        print(
            "İşlenecek bekleyen bağlantı yok."
        )

        return


    basarili_sayi = 0

    hatali_sayi = 0


    for kayit in bekleyenler:

        sonuc = tek_link_isle(
            kayit
        )


        veri_kaydet(
            veri
        )


        if sonuc:

            basarili_sayi += 1

        else:

            hatali_sayi += 1


    print()
    print("==============================")
    print("TOPLU İŞLEM TAMAMLANDI")
    print("==============================")

    print(
        "Başarılı:",
        basarili_sayi
    )

    print(
        "Hatalı:",
        hatali_sayi
    )

    print(
        "Toplam:",
        len(
            bekleyenler
        )
    )



def id_ile_link_isle():

    veri = veri_yukle()


    if veri is None:

        return


    try:

        secilen_id = int(
            input(
                "İşlenecek link ID: "
            )
        )

    except ValueError:

        print(
            "Geçerli bir sayı girmedin."
        )

        return


    for kayit in veri.get(
        "linkler",
        []
    ):

        if kayit.get(
            "id"
        ) == secilen_id:

            tek_link_isle(
                kayit
            )

            veri_kaydet(
                veri
            )

            return


    print(
        "Link bulunamadı."
    )



def aktiflik_degistir():

    veri = veri_yukle()


    if veri is None:

        return


    try:

        secilen_id = int(
            input(
                "Link ID: "
            )
        )

    except ValueError:

        print(
            "Geçerli bir sayı girmedin."
        )

        return


    for kayit in veri.get(
        "linkler",
        []
    ):

        if kayit.get(
            "id"
        ) == secilen_id:

            kayit["aktif"] = not kayit.get(
                "aktif",
                True
            )


            veri_kaydet(
                veri
            )


            print(
                "Yeni aktiflik durumu:",
                kayit["aktif"]
            )

            return


    print(
        "Link bulunamadı."
    )



def link_sil():

    veri = veri_yukle()


    if veri is None:

        return


    try:

        secilen_id = int(
            input(
                "Silinecek link ID: "
            )
        )

    except ValueError:

        print(
            "Geçerli bir sayı girmedin."
        )

        return


    for kayit in veri.get(
        "linkler",
        []
    ):

        if kayit.get(
            "id"
        ) != secilen_id:

            continue


        print()
        print(
            "Silinecek URL:"
        )

        print(
            kayit.get(
                "url",
                ""
            )
        )


        onay = input(
            "Emin misin? (E/H): "
        ).strip().casefold()


        if onay != "e":

            print(
                "Silme işlemi iptal edildi."
            )

            return


        veri["linkler"].remove(
            kayit
        )


        veri_kaydet(
            veri
        )


        print(
            "Link silindi."
        )

        return


    print(
        "Link bulunamadı."
    )



def istatistik_yazdir():

    veri = veri_yukle()


    if veri is None:

        return


    sayaclar = {

        "toplam": 0,

        "bekliyor": 0,

        "tamamlandi": 0,

        "hata": 0,

        "desteklenmiyor": 0,

        "pasif": 0

    }


    for kayit in veri.get(
        "linkler",
        []
    ):

        sayaclar["toplam"] += 1


        if not kayit.get(
            "aktif",
            True
        ):

            sayaclar["pasif"] += 1


        durum = kayit.get(
            "durum",
            "bekliyor"
        )


        if durum in sayaclar:

            sayaclar[durum] += 1


    print()
    print("==============================")
    print("İHALE LİNK İSTATİSTİKLERİ")
    print("==============================")

    print(
        "Toplam:",
        sayaclar["toplam"]
    )

    print(
        "Bekleyen:",
        sayaclar["bekliyor"]
    )

    print(
        "Tamamlanan:",
        sayaclar["tamamlandi"]
    )

    print(
        "Hatalı:",
        sayaclar["hata"]
    )

    print(
        "Desteklenmeyen:",
        sayaclar["desteklenmiyor"]
    )

    print(
        "Pasif:",
        sayaclar["pasif"]
    )



def menu():

    while True:

        print()
        print("================================")
        print("KANTİN RADAR AI")
        print("İHALE LİNK YÖNETİM PANELİ")
        print("================================")
        print()
        print("1 - Yeni ihale linki ekle")
        print("2 - Linkleri listele")
        print("3 - Bekleyen tüm linkleri işle")
        print("4 - ID ile tek link işle")
        print("5 - Aktif/Pasif değiştir")
        print("6 - Link sil")
        print("7 - İstatistikler")
        print("0 - Çıkış")
        print()
        print("================================")


        secim = input(
            "Seçim: "
        ).strip()


        if secim == "1":

            link_ekle()


        elif secim == "2":

            linkleri_listele()


        elif secim == "3":

            bekleyen_linkleri_isle()


        elif secim == "4":

            id_ile_link_isle()


        elif secim == "5":

            aktiflik_degistir()


        elif secim == "6":

            link_sil()


        elif secim == "7":

            istatistik_yazdir()


        elif secim == "0":

            print()
            print(
                "İhale link paneli kapatıldı."
            )

            break


        else:

            print(
                "Geçersiz seçim."
            )


        input(
            "\nDevam etmek için ENTER..."
        )



if __name__ == "__main__":

    menu()