import json
from veri.turkiye_veri import TURKIYE


DOSYA = "kaynak_haritasi.json"


def harita_olustur():

    veri = {
        "Turkiye": {}
    }


    for il, ilceler in TURKIYE.items():

        veri["Turkiye"][il] = {}

        for ilce in ilceler:

            veri["Turkiye"][il][ilce] = {

                "kaynaklar": []

            }


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


    print("====================")
    print("KAYNAK HARİTASI OLUŞTU")
    print("====================")

    print(
        "İl:",
        len(veri["Turkiye"])
    )

    toplam = sum(
        len(x)
        for x in veri["Turkiye"].values()
    )

    print(
        "İlçe:",
        toplam
    )


if __name__ == "__main__":

    harita_olustur()