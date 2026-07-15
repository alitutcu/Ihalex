import requests


def kaynak_kontrol(url):

    print("\nKontrol:")
    print(url)


    try:

        cevap = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )


        print(
            "Durum:",
            cevap.status_code
        )


        print(
            "Boyut:",
            len(cevap.text),
            "karakter"
        )


        if "login" in cevap.text.lower():

            print(
                "UYARI: Giriş sayfası geldi"
            )


        else:

            print(
                "OK: Veri alınabilir"
            )


    except Exception as hata:

        print(
            "HATA:",
            hata
        )



kaynak_kontrol(
    "https://www.sahibinden.com"
)