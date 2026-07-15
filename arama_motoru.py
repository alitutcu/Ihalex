import requests
from bs4 import BeautifulSoup

from kaynak_okuyucu import kaynaklari_getir


def site_tara(url, kelime):

    print("\nTaranıyor:")
    print(url)

    try:

        cevap = requests.get(
            url,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            },
            timeout=10
        )


        if cevap.status_code == 200:

            print("Bağlantı başarılı")


            soup = BeautifulSoup(
                cevap.text,
                "html.parser"
            )


            baslik = soup.title


            if baslik:
                print(
                    "Sayfa:",
                    baslik.text
                )


            # Şimdilik basit arama
            metin = soup.get_text()


            if kelime.lower() in metin.lower():

                print(
                    "Anahtar kelime bulundu:",
                    kelime
                )

            else:

                print(
                    "Kelime bulunamadı"
                )


        else:

            print(
                "Hata kodu:",
                cevap.status_code
            )


    except Exception as hata:

        print(
            "Bağlantı hatası:",
            hata
        )




# ----------------------

bolge = kaynaklari_getir(
    "Samsun",
    "Atakum"
)


arama_kelimesi = [
    "kantin",
    "okul",
    "büfe",
    "kiralık"
]


for kaynak in bolge:


    if kaynak["aktif"]:


        for kelime in arama_kelimesi:

            site_tara(
                kaynak["url"],
                kelime
            )