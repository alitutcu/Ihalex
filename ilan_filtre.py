ANAHTAR_KELIMELER = {


    "kantin":30,

    "okul":25,

    "büfe":20,

    "bufe":20,

    "çay ocağı":15,

    "cay ocagi":15,

    "devren":10,

    "kiralık":5

}



def ilan_analiz_et(baslik):


    baslik = baslik.lower()


    skor = 0


    nedenler = []



    for kelime,puan in ANAHTAR_KELIMELER.items():


        if kelime in baslik:


            skor += puan

            nedenler.append(
                kelime
            )



    if skor >=70:

        durum="ÇOK UYGUN"


    elif skor >=40:

        durum="İNCELENMELİ"


    else:

        durum="DÜŞÜK"



    return {

        "skor":skor,

        "durum":durum,

        "nedenler":nedenler

    }