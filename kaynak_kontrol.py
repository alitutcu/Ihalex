import requests
import json
from datetime import datetime



def kaynak_haritasi_oku():

    with open(
        "kaynak_haritasi.json",
        "r",
        encoding="utf-8"
    ) as dosya:

        return json.load(dosya)




def aktif_kaynaklari_bul(veri):

    liste = []


    iller = veri["Turkiye"]["iller"]


    for il, il_veri in iller.items():

        for ilce, ilce_veri in il_veri["ilceler"].items():

            for kaynak in ilce_veri["kaynaklar"]:

                if kaynak.get("aktif"):

                    liste.append(
                        {
                            "il": il,
                            "ilce": ilce,
                            "site": kaynak["site"],
                            "url": kaynak["url"],
                            "kategori": kaynak.get(
                                "kategori",
                                ""
                            )
                        }
                    )


    return liste





def site_test_et(url):

    sonuc = {

        "durum": "",
        "status_code": None,
        "login": False,
        "otomatik_tarama": True,
        "not": ""

    }


    try:

        cevap = requests.get(

            url,

            headers={
                "User-Agent":
                "Mozilla/5.0"
            },

            timeout=15

        )


        sonuc["status_code"] = cevap.status_code



        if cevap.status_code == 200:


            sonuc["durum"] = "aktif"


            sayfa = cevap.text.lower()



            login_isaretleri = [

                "login",

                "giriş",

                "üye ol",

                "hesabım",

                "oturum aç"

            ]


            for kelime in login_isaretleri:


                if kelime in sayfa:


                    sonuc["login"] = True

                    sonuc["otomatik_tarama"] = False

                    sonuc["not"] = (
                        "Login gerektiriyor"
                    )

                    break



        else:

            sonuc["durum"] = "hata"



    except Exception as hata:


        sonuc["durum"] = "ulaşılamıyor"

        sonuc["not"] = str(hata)



    return sonuc






def rapor_kaydet(veriler):


    with open(

        "kaynak_raporu.json",

        "w",

        encoding="utf-8"

    ) as dosya:


        json.dump(

            veriler,

            dosya,

            ensure_ascii=False,

            indent=4

        )







# -------------------------
# PROGRAM BAŞLANGICI
# -------------------------


print("""
KANTİN RADAR AI
================
ADIM 10
KAYNAK KONTROL MOTORU
================
""")


harita = kaynak_haritasi_oku()


kaynaklar = aktif_kaynaklari_bul(
    harita
)



rapor = []



for kaynak in kaynaklar:


    print("--------------------")

    print(
        kaynak["site"]
    )

    print(
        kaynak["url"]
    )


    sonuc = site_test_et(
        kaynak["url"]
    )


    kayit = {

        **kaynak,

        **sonuc,

        "kontrol_tarihi":
        str(datetime.now())

    }


    rapor.append(
        kayit
    )



    print(
        "Durum:",
        sonuc["durum"]
    )


    if sonuc["login"]:

        print(
            "⚠ Login gerekli"
        )





rapor_kaydet(
    rapor
)



print("""
--------------------
KONTROL TAMAMLANDI

Oluşturulan dosya:
kaynak_raporu.json
""")