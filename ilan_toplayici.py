import requests
from bs4 import BeautifulSoup


def site_tara(url):

    print("\nTaranıyor:")
    print(url)

    try:

        headers = {
            "User-Agent": 
            "Mozilla/5.0"
        }


        cevap = requests.get(
            url,
            headers=headers,
            timeout=10
        )


        if cevap.status_code == 200:

            print("Bağlantı başarılı")

            soup = BeautifulSoup(
                cevap.text,
                "html.parser"
            )


            # Sayfa başlığı
            print(
                "Başlık:",
                soup.title.text
                if soup.title
                else "Yok"
            )


            return soup


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


    return None



# TEST

site_tara(
    "https://www.sahibinden.com"
)