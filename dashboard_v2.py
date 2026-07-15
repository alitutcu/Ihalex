from veritabani import baglan



def baslik():

    print("""
================================
        KANTİN RADAR AI
          DASHBOARD
================================
""")



def istatistik():

    conn = baglan()

    cur = conn.cursor()



    cur.execute(
        """
        SELECT COUNT(*)
        FROM ilanlar
        """
    )


    toplam = cur.fetchone()[0]



    cur.execute(
        """
        SELECT COUNT(*)
        FROM ilanlar
        WHERE puan >= 80
        """
    )


    alarm = cur.fetchone()[0]



    conn.close()



    print(
        "Toplam ilan:",
        toplam
    )


    print(
        "Alarm seviyesi:",
        alarm
    )



def en_iyi_ilanlar():

    conn = baglan()

    cur = conn.cursor()



    cur.execute(
        """
        SELECT

        baslik,
        il,
        ilce,
        puan

        FROM ilanlar

        ORDER BY puan DESC

        LIMIT 10

        """
    )


    ilanlar = cur.fetchall()



    print()

    print("==============================")
    print("EN İYİ FIRSATLAR")
    print("==============================")



    if not ilanlar:

        print(
            "Henüz ilan yok"
        )


    for i, ilan in enumerate(
        ilanlar,
        1
    ):

        print()

        print(
            i,
            ")",
            ilan[0]
        )


        print(
            ilan[1],
            "/",
            ilan[2]
        )


        print(
            "Puan:",
            ilan[3]
        )



    conn.close()





def calistir():

    baslik()

    istatistik()

    en_iyi_ilanlar()



if __name__ == "__main__":

    calistir()