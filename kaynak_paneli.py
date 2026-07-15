import json
import os


DOSYA = "kaynak_haritasi.json"


def veri_yukle():

    if not os.path.exists(DOSYA):

        print("Kaynak haritası bulunamadı!")
        return None

    with open(
        DOSYA,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



def veri_kaydet(veri):

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



def kaynak_ekle():

    veri = veri_yukle()

    if veri is None:
        return


    print("====================")
    print("KAYNAK EKLEME PANELİ")
    print("====================")


    il = input("İl: ")

    if il not in veri["Turkiye"]:

        print("İl bulunamadı")
        return



    ilce = input("İlçe: ")


    if ilce not in veri["Turkiye"][il]:

        print("İlçe bulunamadı")
        return



    site = input("Site adı: ")

    url = input("URL: ")

    kategori = input("Kategori: ")



    yeni = {

        "site": site,

        "url": url,

        "kategori": kategori,

        "aktif": True,

        "bot_korumasi": False,

        "captcha": False,

        "giris_gerekiyor": False,

        "basari_orani": 0,

        "toplam_tarama": 0

    }



    veri["Turkiye"][il][ilce]["kaynaklar"].append(
        yeni
    )


    veri_kaydet(veri)



    print("====================")
    print("KAYNAK EKLENDİ")
    print("====================")



if __name__ == "__main__":

    kaynak_ekle()