import requests


URL = "https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/turkey.geojson"


response = requests.get(URL)


if response.status_code == 200:

    with open(
        "veri/harita/turkiye_iller.geojson",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(response.text)


    print(
        "Türkiye GeoJSON oluşturuldu"
    )

else:

    print(
        "Hata:",
        response.status_code
    )