import json
import os


dosya = "veri/harita/turkiye_iller.geojson"


geojson = {

    "type": "FeatureCollection",

    "features": []

}



with open(
    dosya,
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
    "GeoJSON dosyası oluşturuldu"
)