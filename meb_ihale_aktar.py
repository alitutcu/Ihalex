import sys
from datetime import datetime
from urllib.parse import urlparse

from meb_icerik_okuyucu import meb_icerik_oku
from meb_ek_veri_cikarici import ana_program as ihale_verisi_cikar
from meb_ihale_kaydet import ana_program as ihale_veritabanina_kaydet


def meb_url_gecerli_mi(url):

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


        if (
            "meb.gov.tr"
            not in adres.netloc.lower()
        ):

            return False


        return True


    except Exception:

        return False



def baslik_yazdir():

    print()
    print("====================================")
    print("KANTİN RADAR AI")
    print("MEB İHALE TEK KOMUT AKTARIM MOTORU")
    print("====================================")



def adim_yazdir(
        adim,
        toplam,
        aciklama
):

    print()
    print("------------------------------------")

    print(
        f"ADIM {adim}/{toplam}"
    )

    print(
        aciklama
    )

    print("------------------------------------")



def meb_ihale_aktar(url):

    baslik_yazdir()


    if not meb_url_gecerli_mi(
        url
    ):

        print()
        print(
            "HATA: Geçerli bir MEB bağlantısı girilmedi."
        )

        print(
            "Örnek:"
        )

        print(
            "https://mamak.meb.gov.tr/"
            "www/kantin-ihalesi/icerik/2619"
        )

        return False


    baslangic = datetime.now()


    print()
    print(
        "Kaynak URL:"
    )

    print(url)

    print(
        "Başlangıç:",
        baslangic.strftime(
            "%d.%m.%Y %H:%M:%S"
        )
    )


    try:

        adim_yazdir(
            1,
            3,
            "MEB içerik sayfası okunuyor "
            "ve ek dosyalar indiriliyor."
        )


        sayfa_sonucu = meb_icerik_oku(
            url
        )


        if sayfa_sonucu is None:

            print()
            print(
                "HATA: MEB sayfası okunamadı."
            )

            return False


        ek_sayisi = sayfa_sonucu.get(
            "ek_sayisi",
            0
        )


        print()
        print(
            "İçerik sayfası okundu."
        )

        print(
            "Bulunan ek dosya:",
            ek_sayisi
        )


        if ek_sayisi == 0:

            print()
            print(
                "UYARI: Sayfada indirilebilir "
                "PDF veya DOCX bulunamadı."
            )

            print(
                "Yine de belge analiz adımı çalıştırılacak."
            )


        adim_yazdir(
            2,
            3,
            "PDF ve DOCX belgelerinden "
            "ihale bilgileri çıkarılıyor."
        )


        ihale_verisi_cikar()


        adim_yazdir(
            3,
            3,
            "Çıkarılan ihale verisi "
            "SQLite veritabanına kaydediliyor."
        )


        ihale_veritabanina_kaydet()


        bitis = datetime.now()

        sure = (
            bitis
            -
            baslangic
        ).total_seconds()


        print()
        print("====================================")
        print("MEB İHALE AKTARIMI TAMAMLANDI")
        print("====================================")

        print(
            "Kaynak:",
            url
        )

        print(
            "Bitiş:",
            bitis.strftime(
                "%d.%m.%Y %H:%M:%S"
            )
        )

        print(
            "İşlem süresi:",
            round(
                sure,
                1
            ),
            "saniye"
        )

        print(
            "Veritabanı:",
            "ilanlar.db"
        )

        print(
            "İçerik çıktısı:",
            "meb_icerik_sonucu.json"
        )

        print(
            "İhale çıktısı:",
            "meb_ihale_verisi.json"
        )

        print("====================================")


        return True


    except KeyboardInterrupt:

        print()
        print(
            "İşlem kullanıcı tarafından durduruldu."
        )

        return False


    except Exception as hata:

        print()
        print("====================================")
        print("AKTARIM HATASI")
        print("====================================")

        print(
            hata
        )

        return False



def url_al():

    print()
    print(
        "MEB ihale veya duyuru linkini gir:"
    )


    url = input(
        "> "
    ).strip()


    return url



def main():

    if len(
        sys.argv
    ) > 1:

        url = sys.argv[1].strip()

    else:

        url = url_al()


    basarili = meb_ihale_aktar(
        url
    )


    if basarili:

        print()
        print(
            "İşlem başarıyla tamamlandı."
        )

    else:

        print()
        print(
            "İşlem tamamlanamadı."
        )



if __name__ == "__main__":

    main()