from datetime import datetime



def ilan_olustur(
        baslik="",
        aciklama="",
        il="",
        ilce="",
        adres="",
        fiyat=None,
        alan=None,
        kaynak="",
        url=""
):

    ilan = {

        "baslik": baslik,

        "aciklama": aciklama,

        "il": il,

        "ilce": ilce,

        "adres": adres,

        "fiyat": fiyat,

        "alan": alan,

        "kaynak": kaynak,

        "url": url,

        "puan": 0,

        "durum": "yeni",

        "eklenme_tarihi":
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    }


    return ilan



def ilan_yazdir(ilan):

    print("====================")
    print("İLAN BİLGİSİ")
    print("====================")

    print(
        "Başlık:",
        ilan["baslik"]
    )

    print(
        "Konum:",
        ilan["il"],
        "/",
        ilan["ilce"]
    )

    print(
        "Fiyat:",
        ilan["fiyat"]
    )

    print(
        "Alan:",
        ilan["alan"]
    )

    print(
        "Kaynak:",
        ilan["kaynak"]
    )

    print(
        "Puan:",
        ilan["puan"]
    )

    print("====================")



if __name__ == "__main__":


    test = ilan_olustur(

        baslik="Okul kantini devren kiralık",

        il="Samsun",

        ilce="Atakum",

        fiyat=120000,

        alan=50,

        kaynak="Sahibinden",

        url="https://..."

    )


    ilan_yazdir(test)