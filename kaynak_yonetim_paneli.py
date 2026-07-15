import json
import os


DOSYA = "kaynak_haritasi.json"


def yukle():

    if not os.path.exists(DOSYA):

        print("Kaynak haritası bulunamadı")
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



def kaynaklari_listele(veri):

    print("\n====================")
    print("KAYNAK LİSTESİ")
    print("====================")


    sayac = 0


    for il, ilceler in veri["Turkiye"].items():

        for ilce, bilgi in ilceler.items():

            for kaynak in bilgi["kaynaklar"]:

                sayac += 1

                durum = "AKTİF" if kaynak["aktif"] else "PASİF"

                print(
                    f"{sayac}) {il} / {ilce}"
                )

                print(
                    "   Site:",
                    kaynak["site"]
                )

                print(
                    "   URL:",
                    kaynak["url"]
                )

                print(
                    "   Durum:",
                    durum
                )


    if sayac == 0:

        print("Henüz kaynak yok")



def kaynak_durum_degistir(veri):

    il = input("İl: ")

    ilce = input("İlçe: ")

    site = input("Site adı: ")



    kaynaklar = veri["Turkiye"][il][ilce]["kaynaklar"]


    for kaynak in kaynaklar:

        if kaynak["site"] == site:

            kaynak["aktif"] = not kaynak["aktif"]

            kaydet(veri)

            print(
                "Durum değiştirildi"
            )

            return


    print(
        "Kaynak bulunamadı"
    )



def kaynak_sil(veri):

    il = input("İl: ")

    ilce = input("İlçe: ")

    site = input("Site adı: ")


    kaynaklar = veri["Turkiye"][il][ilce]["kaynaklar"]


    for kaynak in kaynaklar:

        if kaynak["site"] == site:

            kaynaklar.remove(kaynak)

            kaydet(veri)

            print(
                "Kaynak silindi"
            )

            return


    print(
        "Kaynak bulunamadı"
    )



def menu():

    veri = yukle()

    if veri is None:
        return


    while True:

        print("""
====================
KAYNAK YÖNETİM PANELİ
====================

1 - Kaynakları listele

2 - Aktif/Pasif değiştir

3 - Kaynak sil

0 - Çıkış

====================
""")


        secim = input("Seçim: ")


        if secim == "1":

            kaynaklari_listele(veri)


        elif secim == "2":

            kaynak_durum_degistir(veri)


        elif secim == "3":

            kaynak_sil(veri)


        elif secim == "0":

            break


        else:

            print(
                "Geçersiz seçim"
            )



if __name__ == "__main__":

    menu()