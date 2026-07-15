import json

from kaynak_secici import taranabilir_kaynaklar


try:

    from playwright_tarayici import ilanlari_tara

except:

    ilanlari_tara = None



def requests_tara(url):

    print(
        "REQUESTS TARAMA:",
        url
    )

    # sonraki aşamada gerçek parser bağlanacak

    return []



def playwright_tara(url):

    print(
        "PLAYWRIGHT TARAMA:",
        url
    )


    if ilanlari_tara:

        try:

            return ilanlari_tara(
                url
            )

        except Exception as hata:

            print(
                "Playwright hata:",
                hata
            )

            return []


    return []



def taramayi_baslat():


    kaynaklar = taranabilir_kaynaklar()


    print("====================")
    print("KANTİN RADAR AI")
    print("AKILLI TARAMA")
    print("====================")


    tum_ilanlar = []



    for kaynak in kaynaklar:


        print()

        print(
            "Kaynak:",
            kaynak["site"]
        )

        print(
            "Bölge:",
            kaynak["il"],
            "/",
            kaynak["ilce"]
        )

        print(
            "Motor:",
            kaynak["motor"]
        )



        if kaynak["motor"] == "playwright":

            ilanlar = playwright_tara(
                kaynak["url"]
            )


        else:

            ilanlar = requests_tara(
                kaynak["url"]
            )



        tum_ilanlar.extend(
            ilanlar
        )



    print()
    print("====================")

    print(
        "Toplam ilan:",
        len(tum_ilanlar)
    )

    print("====================")



    return tum_ilanlar



if __name__ == "__main__":

    taramayi_baslat()