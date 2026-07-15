def arama_url_olustur(
    site,
    sehir,
    ilce,
    kelime
):


    if site == "Sahibinden":


        url = (
            "https://www.sahibinden.com/"
            "arama?"
            "query_text="
            + kelime.replace(" ","+")
        )


        return url



    return None





# TEST

url = arama_url_olustur(
    "Sahibinden",
    "Samsun",
    "Atakum",
    "kantin"
)


print("Oluşturulan URL:")
print(url)