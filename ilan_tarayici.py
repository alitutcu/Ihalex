import json


DOSYA = "kaynak_haritasi.json"



def kaynaklari_getir(il, ilce):

    with open(
        DOSYA,
        "r",
        encoding="utf-8"
    ) as dosya:

        veri = json.load(dosya)


    kaynaklar = veri["Turkiye"]["iller"][il]["ilceler"][ilce]["kaynaklar"]

    return kaynaklar



def ilanlari_tara(il, ilce):

    kaynaklar = kaynaklari_getir(il, ilce)


    print("\nKANTIN RADAR AI")
    print("--------------------")

    print("Bölge:",
          il,
          "-",
          ilce)


    print("\nAktif kaynaklar:")


    for kaynak in kaynaklar:

        if kaynak["aktif"]:

            print(
                "-",
                kaynak["site"],
                kaynak["url"]
            )



# TEST

ilanlari_tara(
    "Samsun",
    "Atakum"
)