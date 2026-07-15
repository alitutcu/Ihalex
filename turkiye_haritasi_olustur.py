import json
import os



ILCE_DOSYASI = "turkiye_ilceler.json"

CIKTI_DOSYASI = "kaynak_haritasi.json"




def ilce_verisi_oku():


    if not os.path.exists(ILCE_DOSYASI):

        print(
            "HATA: turkiye_ilceler.json bulunamadı."
        )

        return None



    try:


        with open(

            ILCE_DOSYASI,

            "r",

            encoding="utf-8-sig"

        ) as f:


            veri = json.load(f)



    except json.JSONDecodeError:


        print(
            "HATA: turkiye_ilceler.json bozuk JSON formatında."
        )

        return None



    except Exception as hata:


        print(
            "Dosya okuma hatası:"
        )

        print(hata)

        return None



    if not veri:


        print(
            "HATA: turkiye_ilceler.json boş."
        )

        return None



    return veri





def harita_olustur():



    ilceler = ilce_verisi_oku()



    if ilceler is None:

        return




    if os.path.exists(CIKTI_DOSYASI):


        cevap = input(

            "\nkaynak_haritasi.json zaten var. Üzerine yazılsın mı? (E/H): "

        )


        if cevap.lower() != "e":


            print(
                "İşlem iptal edildi."
            )

            return





    harita = {


        "Turkiye": {


            "iller": {}

        }

    }



    toplam_il = 0

    toplam_ilce = 0




    for il, ilce_listesi in ilceler.items():



        toplam_il += 1



        harita["Turkiye"]["iller"][il] = {


            "ilceler": {}

        }




        for ilce in ilce_listesi:



            harita["Turkiye"]["iller"][il]["ilceler"][ilce] = {


                "kaynaklar": []

            }



            toplam_ilce += 1





    with open(

        CIKTI_DOSYASI,

        "w",

        encoding="utf-8"

    ) as f:



        json.dump(

            harita,

            f,

            ensure_ascii=False,

            indent=4

        )





    print("\n====================")

    print("TÜRKİYE HARİTASI HAZIR")

    print("====================")


    print(

        "İl sayısı:",

        toplam_il

    )


    print(

        "İlçe sayısı:",

        toplam_ilce

    )


    print(

        "Dosya:",

        CIKTI_DOSYASI

    )





if __name__ == "__main__":


    harita_olustur()