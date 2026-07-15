from playwright.sync_api import sync_playwright
import json


def sayfa_baslik_oku(url):

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        page.goto(
            url,
            timeout=60000
        )

        page.wait_for_timeout(5000)


        veri = {

            "url": url,

            "baslik": page.title(),

            "icerik": page.locator("body").inner_text()[:2000]

        }


        browser.close()


        return veri



url = "https://www.sahibinden.com"


sonuc = sayfa_baslik_oku(url)


print("----------------")
print("KANTİN RADAR AI")
print("----------------")

print(
    sonuc["baslik"]
)


print(
    sonuc["icerik"]
)



with open(
    "sayfa_test.json",
    "w",
    encoding="utf-8"
) as dosya:

    json.dump(
        sonuc,
        dosya,
        ensure_ascii=False,
        indent=4
    )


print("\nKaydedildi.")