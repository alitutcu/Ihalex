import json

from turkiye_veri import TURKIYE



with open(

    "veri/turkiye_ilceler.json",

    "w",

    encoding="utf-8"

) as f:


    json.dump(

        TURKIYE,

        f,

        ensure_ascii=False,

        indent=4

    )




ilce = sum(

    len(x)

    for x in TURKIYE.values()

)



print("====================")

print("VERİ PAKETİ OLUŞTU")

print("====================")

print(
    "İl:",
    len(TURKIYE)
)

print(
    "İlçe:",
    ilce
)