import json
import os
import requests
from datetime import datetime


DOSYA = "kaynak_haritasi.json"


def yukle():

    if not os.path.exists(DOSYA):

        print("Kaynak dosyası bulunamadı")
        return None


    with open(
        DOSYA,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



def kaydet(veri):

    with open(
        DOSYA,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            veri,
            f,
            ensure_ascii=False,
            indent=4
        )



def kontrol_et(url):

    try:

        cevap = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )


        return {

            "durum": True,

            "kod":
            cevap.status_code,

            "bot":
            False

        }


    except Exception as hata:


        return {

            "durum": False,

            "kod": None,

            "bot": False,

            "hata": str(hata)

        }



def kaynaklari_kontrol_et():

    veri = yukle()

    if veri is None:
        return



    toplam = 0
    basarili = 0


    print("====================")
    print("KAYNAK SAĞLIK KONTROLÜ")
    print("====================")


    for il, ilceler in veri["Turkiye"].items():


        for ilce, bilgi in ilceler.items():


            for kaynak in bilgi["kaynaklar"]:


                toplam += 1


                sonuc = kontrol_et(
                    kaynak["url"]
                )


                kaynak["son_kontrol"] = (
                    datetime.now()
                    .strftime(
                        "%Y-%m-%d %H:%M"
                    )
                )


                kaynak["durum"] = (
                    "aktif"
                    if sonuc["durum"]
                    else "kapali"
                )


                kaynak["http_kodu"] = (
                    sonuc["kod"]
                )


                kaynak["bot_korumasi"] = (
                    sonuc["bot"]
                )


                if sonuc["durum"]:
                    basarili += 1



                print(
                    il,
                    "/",
                    ilce,
                    "/",
                    kaynak["site"],
                    "->",
                    kaynak["durum"]
                )



    kaydet(veri)


    print("====================")
    print(
        "Toplam kaynak:",
        toplam
    )

    print(
        "Başarılı:",
        basarili
    )



if __name__ == "__main__":

    kaynaklari_kontrol_et()