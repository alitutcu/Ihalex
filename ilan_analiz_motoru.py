from veritabani import baglan



def puan_hesapla(ilan):

    puan = 0


    baslik = (
        ilan["baslik"]
        or ""
    ).lower()


    il = (
        ilan["il"]
        or ""
    )


    alan = ilan["alan"]


    fiyat = ilan["fiyat"]



    # 1 - Kantin kelime analizi

    kelimeler = [

        "kantin",

        "okul",

        "devren",

        "kiralık",

        "işletme"

    ]


    for kelime in kelimeler:

        if kelime in baslik:

            puan += 10



    # 2 - Bölge puanı

    if il:

        puan += 20



    # 3 - Alan değerlendirme

    try:

        alan = int(alan)


        if alan >= 30:

            puan += 20


        elif alan >= 15:

            puan += 10


    except:

        pass



    # 4 - Fiyat değerlendirme

    try:

        fiyat = int(fiyat)


        if fiyat < 150000:

            puan += 20


        elif fiyat < 300000:

            puan += 10


    except:

        pass



    if puan > 100:

        puan = 100



    return puan





def analiz_et():


    conn = baglan()

    cur = conn.cursor()



    cur.execute(
        """
        SELECT 
        id,
        baslik,
        il,
        alan,
        fiyat

        FROM ilanlar
        """
    )


    ilanlar = cur.fetchall()



    print("====================")
    print("İLAN ANALİZ MOTORU")
    print("====================")



    for ilan in ilanlar:


        veri = {

            "baslik": ilan[1],

            "il": ilan[2],

            "alan": ilan[3],

            "fiyat": ilan[4]

        }



        puan = puan_hesapla(
            veri
        )


        cur.execute(
            """
            UPDATE ilanlar

            SET puan=?

            WHERE id=?

            """,

            (
                puan,
                ilan[0]
            )
        )



        print(
            ilan[1],
            "=>",
            puan,
            "/100"
        )



    conn.commit()

    conn.close()



if __name__ == "__main__":

    analiz_et()
    