import json
import os


DOSYA = "kaynak_haritasi.json"



def kaynaklari_getir():


    liste = []


    if not os.path.exists(DOSYA):

        print(
            "Kaynak haritası bulunamadı"
        )

        return liste



    with open(

        DOSYA,

        "r",

        encoding="utf-8"

    ) as f:

        veri = json.load(f)



    turkiye = veri.get(
        "Turkiye",
        {}
    )



    for il, il_veri in turkiye.items():



        for ilce, ilce_veri in il_veri.items():



            kaynaklar = ilce_veri.get(
                "kaynaklar",
                []
            )



            for kaynak in kaynaklar:



                if kaynak.get(
                    "aktif",
                    False
                ):



                    kaynak_kopya = kaynak.copy()



                    kaynak_kopya["il"] = il

                    kaynak_kopya["ilce"] = ilce



                    liste.append(
                        kaynak_kopya
                    )



    return liste





if __name__ == "__main__":


    kaynaklar = kaynaklari_getir()



    print("====================")

    print(
        "AKTİF KAYNAK SAYISI:",
        len(kaynaklar)
    )

    print("====================")



    if len(kaynaklar)==0:

        print(
            "Aktif kaynak bulunamadı"
        )


    else:


        for kaynak in kaynaklar:


            print(

                kaynak["il"],

                "/",

                kaynak["ilce"],

                "/",

                kaynak["site"]

            )