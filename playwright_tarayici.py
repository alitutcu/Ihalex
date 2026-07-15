from playwright.sync_api import sync_playwright
import time
import os



PROFIL_KLASORU = "tarayici_profili"
HEADLESS = os.getenv("TARAYICI_GORUNUR", "0") != "1"



def ilanlari_tara(url):


    ilanlar = []


    print("\n====================")
    print("PLAYWRIGHT TARAMA")
    print("====================")


    print(
        "Sayfa açılıyor:"
    )

    print(url)



    with sync_playwright() as p:


        context = None



        try:


            # Kalıcı Chrome profili

            context = p.chromium.launch_persistent_context(

                user_data_dir=PROFIL_KLASORU,

                headless=HEADLESS,

                viewport={
                    "width":1280,
                    "height":900
                },

                locale="tr-TR"

            )



            page = context.new_page()



            page.goto(

                url,

                wait_until="load",

                timeout=60000

            )



            print(
                "\nSayfa yüklendi"
            )


            time.sleep(5)



            print(
                "\nBaşlık:"
            )


            print(
                page.title()
            )



            print(
                "\nAktif URL:"
            )


            print(
                page.url
            )



            ########################
            # LOGIN KONTROLÜ
            ########################


            if "secure.sahibinden.com" in page.url:

                if HEADLESS:
                    print("Giris gerekiyor; gorunmez worker bu kaynagi atladi.")
                    return []


                print(
                    "\n⚠ LOGIN GEREKLİ"
                )


                print(
                    "Tarayıcıda giriş yapıp ENTER'a basın..."
                )


                input()



                page.goto(

                    url,

                    wait_until="load",

                    timeout=60000

                )


                time.sleep(5)




            ########################
            # BOT KONTROLÜ
            ########################


            html = page.content().lower()



            if (

                "captcha" in html

                or

                "cloudflare" in html

            ):


                print(
                    "\nBOT KORUMASI ALGILANDI"
                )


                page.screenshot(

                    path="bot_korumasi.png"

                )


                return []



            ########################
            # İLAN TOPLAMA
            ########################


            print(
                "\nİlanlar aranıyor..."
            )



            linkler = page.locator(

                "a[href*='/ilan/']"

            )


            adet = linkler.count()



            print(
                "Bulunan link:",
                adet
            )



            for i in range(adet):


                try:


                    element = linkler.nth(i)



                    href = element.get_attribute(

                        "href"

                    )



                    baslik = element.inner_text()



                    if href:


                        if href.startswith("/"):


                            href = (

                                "https://www.sahibinden.com"

                                + href

                            )



                        ilanlar.append(

                            {

                                "baslik":
                                baslik.strip(),


                                "url":
                                href

                            }

                        )



                except:


                    continue



            ########################
            # TEKRAR TEMİZLEME
            ########################


            temiz=[]

            gorulen=set()



            for ilan in ilanlar:


                if ilan["url"] not in gorulen:


                    temiz.append(ilan)


                    gorulen.add(
                        ilan["url"]
                    )



            ilanlar=temiz



            print(

                "\nTemiz ilan sayısı:",

                len(ilanlar)

            )



        except Exception as hata:


            print(
                "\nHATA:"
            )

            print(hata)



        finally:


            if context:


                context.close()



    return ilanlar
