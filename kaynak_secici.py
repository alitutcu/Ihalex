import json
import os


DOSYA = "kaynak_haritasi.json"



def yukle():

    if not os.path.exists(DOSYA):

        print("Kaynak dosyası yok")

        return None


    with open(
        DOSYA,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)




def taranabilir_kaynaklar():

    veri = yukle()


    if veri is None:

        return []



    sonuc = []



    for il, il_veri in veri["Turkiye"].items():


        for ilce, ilce_veri in il_veri.items():


            for kaynak in ilce_veri.get(
                "kaynaklar",
                []
            ):



                if not kaynak.get(
                    "aktif",
                    False
                ):

                    continue



                motor = "requests"



                if kaynak.get(
                    "bot_korumasi",
                    False
                ):

                    motor = "playwright"




                sonuc.append(

                    {

                        "il": il,

                        "ilce": ilce,

                        "site": kaynak["site"],

                        "url": kaynak["url"],

                        "motor": motor

                    }

                )



    return sonuc





if __name__ == "__main__":


    kaynaklar = taranabilir_kaynaklar()


    print("====================")
    print("AKILLI KAYNAK SEÇİCİ")
    print("====================")



    for kaynak in kaynaklar:


        print(

            kaynak["il"],

            "/",

            kaynak["ilce"],

            "/",

            kaynak["site"],

            "→",

            kaynak["motor"]

        )



    print("====================")

    print(
        "Toplam:",
        len(kaynaklar)
    )