import json


DOSYA = "kaynak_haritasi.json"


def dosya_oku():

    with open(
        DOSYA,
        "r",
        encoding="utf-8"
    ) as dosya:

        return json.load(dosya)



def dosyaya_yaz(veri):

    with open(
        DOSYA,
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            veri,
            dosya,
            indent=4,
            ensure_ascii=False
        )



def kaynak_ekle(
        il,
        ilce,
        site,
        url,
        tip="ilan"
):

    veri = dosya_oku()


    yeni_kaynak = {

        "site": site,
        "url": url,
        "tip": tip,
        "aktif": True,
        "not": ""

    }


    veri["Turkiye"]["iller"][il]["ilceler"][ilce]["kaynaklar"].append(
        yeni_kaynak
    )


    dosyaya_yaz(veri)


    print("Kaynak eklendi")



# TEST

kaynak_ekle(
    "Samsun",
    "Atakum",
    "Sahibinden",
    "https://www.sahibinden.com"
)