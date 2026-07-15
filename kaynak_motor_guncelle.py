import json
import os


DOSYA = "kaynak_haritasi.json"


def veri_yukle():

    if not os.path.exists(DOSYA):

        print(
            "HATA: kaynak_haritasi.json bulunamadı."
        )

        return None


    try:

        with open(
            DOSYA,
            "r",
            encoding="utf-8"
        ) as dosya:

            return json.load(dosya)


    except json.JSONDecodeError as hata:

        print(
            "HATA: JSON dosyası bozuk."
        )

        print(hata)

        return None


    except Exception as hata:

        print(
            "Dosya okuma hatası:"
        )

        print(hata)

        return None



def veri_kaydet(veri):

    with open(
        DOSYA,
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            veri,
            dosya,
            ensure_ascii=False,
            indent=4
        )



def kaynak_motorunu_guncelle(
        il,
        ilce,
        site
):

    veri = veri_yukle()

    if veri is None:

        return False


    turkiye = veri.get(
        "Turkiye",
        {}
    )


    if il not in turkiye:

        print(
            "HATA: İl bulunamadı:",
            il
        )

        return False


    if ilce not in turkiye[il]:

        print(
            "HATA: İlçe bulunamadı:",
            ilce
        )

        return False


    kaynaklar = turkiye[il][ilce].get(
        "kaynaklar",
        []
    )


    for kaynak in kaynaklar:

        if kaynak.get(
            "site",
            ""
        ).casefold() == site.casefold():

            kaynak["aktif"] = True

            kaynak["motor"] = "playwright"

            kaynak["bot_korumasi"] = True

            kaynak["captcha"] = False

            kaynak["giris_gerekiyor"] = False

            kaynak["not"] = (
                "Dinamik içerik nedeniyle "
                "Playwright ile taranacak."
            )


            veri_kaydet(
                veri
            )


            print("====================")

            print("KAYNAK GÜNCELLENDİ")

            print("====================")

            print(
                "İl:",
                il
            )

            print(
                "İlçe:",
                ilce
            )

            print(
                "Site:",
                kaynak["site"]
            )

            print(
                "Motor:",
                kaynak["motor"]
            )

            print(
                "Bot koruması:",
                kaynak["bot_korumasi"]
            )

            return True


    print(
        "HATA: Kaynak bulunamadı:",
        site
    )

    return False



if __name__ == "__main__":

    kaynak_motorunu_guncelle(
        il="Samsun",
        ilce="Atakum",
        site="Sahibinden"
    )