from kaynak_okuyucu import kaynaklari_getir

from arama_url_motoru import arama_url_olustur

from ilan_yakalayici import ilanlari_tara_ve_kaydet



ARAMA_KELIMELERI = [

    "kantin",

    "okul kantini",

    "büfe",

    "çay ocağı",

    "devren kiralık"

]




def tum_kaynaklari_tara():


    print("\n====================")

    print("KANTİN RADAR AI")

    print("OTOMATİK TARAMA")

    print("====================")



    kaynaklar = kaynaklari_getir()



    toplam = 0



    for kaynak in kaynaklar:



        if not kaynak.get(
            "aktif",
            False
        ):

            continue



        site = kaynak["site"]


        url = kaynak["url"]



        print("\n----------------")

        print(
            "Kaynak:",
            site
        )



        for kelime in ARAMA_KELIMELERI:



            print(

                "\nArama:",

                kelime

            )



            arama_url = arama_url_olustur(

                kelime

            )



            sonuc = ilanlari_tara_ve_kaydet(

                arama_url,

                site,

                kaynak.get(
                    "il",
                    ""
                ),

                kaynak.get(
                    "ilce",
                    ""
                )

            )



            toplam += sonuc



    print("\n====================")

    print(

        "Toplam yeni ilan:",

        toplam

    )

    print("====================")




if __name__ == "__main__":


    tum_kaynaklari_tara()