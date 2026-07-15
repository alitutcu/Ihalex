import json


iller = [
    "Adana",
    "Adıyaman",
    "Afyonkarahisar",
    "Ankara",
    "Antalya",
    "Aydın",
    "Balıkesir",
    "Bursa",
    "Denizli",
    "Diyarbakır",
    "Edirne",
    "Erzurum",
    "Eskişehir",
    "Gaziantep",
    "Hatay",
    "İstanbul",
    "İzmir",
    "Kocaeli",
    "Konya",
    "Malatya",
    "Manisa",
    "Mersin",
    "Muğla",
    "Samsun",
    "Sakarya",
    "Trabzon",
    "Şanlıurfa",
    "Tekirdağ",
    "Van",
    "Yalova",
    "Zonguldak"
]


features = []


for il in iller:

    feature = {

        "type": "Feature",

        "properties": {

            "name": il

        },

        "geometry": {

            "type": "Polygon",

            "coordinates": []

        }

    }


    features.append(feature)



geojson = {

    "type": "FeatureCollection",

    "features": features

}



with open(

    "veri/harita/turkiye_iller.geojson",

    "w",

    encoding="utf-8"

) as f:


    json.dump(

        geojson,

        f,

        ensure_ascii=False,

        indent=4

    )



print(
    "GeoJSON oluşturuldu:",
    len(features),
    "il"
)