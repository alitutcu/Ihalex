from playwright_tarayici import ilanlari_tara
from veritabani import ilan_kaydet
from ilan_filtre import ilan_analiz_et
from ilan_modeli import ilan_olustur



def ilanlari_tara_ve_kaydet(

        url,

        kaynak,

        il="Samsun",

        ilce="Atakum"

):


    print("\n====================")
    print("KANTİN RADAR AI")
    print("İLAN TARAMA BAŞLADI")
    print("====================")


    ilanlar = ilanlari_tara(url)



    print(
        "\nBulunan ilan:",
        len(ilanlar)
    )



    kayit = 0



    for ilan in ilanlar:


        baslik = ilan["baslik"]

        link = ilan["url"]



        analiz = ilan_analiz_et(
            baslik
        )



        print("\n----------------")
        print(
            baslik
        )

        print(
            "Skor:",
            analiz["skor"]
        )

        print(
            "Durum:",
            analiz["durum"]
        )



        if analiz["skor"] < 20:

            print(
                "Atlandı: düşük uygunluk"
            )

            continue



        yeni_ilan = ilan_olustur(
            baslik=baslik,
            il=il,
            ilce=ilce,
            kaynak=kaynak,
            url=link,
        )
        yeni_ilan.update(puan=analiz["skor"], durum=analiz["durum"])
        sonuc = ilan_kaydet(yeni_ilan)



        if sonuc:

            kayit += 1



    print("\n====================")

    print(
        "Yeni kayıt:",
        kayit
    )

    print("====================")



    return kayit





# DOĞRUDAN ÇALIŞTIRMA TESTİ

if __name__ == "__main__":


    test_url = (

        "https://www.sahibinden.com/"
        "arama?query_text=kantin"

    )


    ilanlari_tara_ve_kaydet(

        test_url,

        "Sahibinden",

        "Samsun",

        "Atakum"

    )
