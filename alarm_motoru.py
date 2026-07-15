from veritabani import baglan
from datetime import datetime



def alarm_seviyesi(puan):

    if puan >= 90:

        return "ACİL"


    elif puan >= 80:

        return "ÖNEMLİ"


    elif puan >= 60:

        return "TAKİP"


    else:

        return "NORMAL"





def alarm_kontrol():


    conn = baglan()

    cur = conn.cursor()



    cur.execute(
        """
        SELECT

        id,
        baslik,
        il,
        ilce,
        puan

        FROM ilanlar

        ORDER BY puan DESC

        """
    )



    ilanlar = cur.fetchall()



    print("====================")
    print("ALARM MOTORU")
    print("====================")



    alarm_sayisi = 0



    for ilan in ilanlar:


        seviye = alarm_seviyesi(
            ilan[4]
        )


        if seviye != "NORMAL":

            alarm_sayisi += 1


            print()

            print(
                "SEVİYE:",
                seviye
            )


            print(
                "İlan:",
                ilan[1]
            )


            print(
                "Konum:",
                ilan[2],
                "/",
                ilan[3]
            )


            print(
                "Puan:",
                ilan[4]
            )


            print(
                "Tarih:",
                datetime.now()
                .strftime(
                    "%Y-%m-%d %H:%M"
                )
            )



    print()

    print("====================")

    print(
        "Alarm:",
        alarm_sayisi
    )

    print("====================")



    conn.close()



if __name__ == "__main__":

    alarm_kontrol()