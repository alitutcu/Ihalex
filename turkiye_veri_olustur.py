import json


DOSYA = "turkiye_ilceler.json"



turkiye = {

    "Samsun": [
        "Atakum",
        "İlkadım",
        "Canik",
        "Bafra",
        "Çarşamba",
        "Terme",
        "Vezirköprü"
    ],


    "İstanbul": [
        "Kadıköy",
        "Beşiktaş",
        "Üsküdar",
        "Bakırköy",
        "Pendik",
        "Esenyurt",
        "Başakşehir"
    ],


    "Ankara": [
        "Çankaya",
        "Keçiören",
        "Mamak",
        "Etimesgut",
        "Sincan",
        "Yenimahalle"
    ],


    "İzmir": [
        "Konak",
        "Karşıyaka",
        "Bornova",
        "Buca",
        "Çiğli"
    ],


    "Bursa": [
        "Osmangazi",
        "Nilüfer",
        "Yıldırım"
    ],


    "Antalya": [
        "Muratpaşa",
        "Kepez",
        "Konyaaltı"
    ]

}



with open(

    DOSYA,

    "w",

    encoding="utf-8"

) as f:


    json.dump(

        turkiye,

        f,

        ensure_ascii=False,

        indent=4

    )



toplam = sum(

    len(x)

    for x in turkiye.values()

)



print("====================")

print("TÜRKİYE VERİ DOSYASI HAZIR")

print("====================")

print("İl:", len(turkiye))

print("İlçe:", toplam)

print("Dosya:", DOSYA)