from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kaynak_okuyucu import kaynaklari_getir

from dashboard import sistem_durumu

from ilan_yakalayici import ilanlari_tara_ve_kaydet

from arama_url_motoru import arama_url_olustur


console = Console()



def baslik():

    console.print(
        Panel(
            """
███████╗ █████╗ ███╗   ██╗████████╗██╗███╗   ██╗
██╔════╝██╔══██╗████╗  ██║╚══██╔══╝██║████╗  ██║
█████╗  ███████║██╔██╗ ██║   ██║   ██║██╔██╗ ██║
██╔══╝  ██╔══██║██║╚██╗██║   ██║   ██║██║╚██╗██║
██║     ██║  ██║██║ ╚████║   ██║   ██║██║ ╚████║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝


          KANTİN RADAR AI
          İlan Analiz Sistemi

            """,
            border_style="cyan"
        )
    )



def menu():

    table = Table(
        title="ANA MENÜ",
        show_header=True,
        header_style="bold cyan"
    )


    table.add_column("No")
    table.add_column("İşlem")


    table.add_row(
        "1",
        "Kaynakları Göster"
    )

    table.add_row(
        "2",
        "Sistem Durumu"
    )

    table.add_row(
        "3",
        "İlan Taraması Başlat"
    )

    table.add_row(
        "4",
        "Çıkış"
    )


    console.print(table)



def kaynaklari_goster():

    console.print(
        Panel(
            "AKTİF KAYNAKLAR",
            border_style="green"
        )
    )


    kaynaklar = kaynaklari_getir()


    for kaynak in kaynaklar:

        console.print(
            f"""
[bold]{kaynak['site']}[/bold]

URL:
{kaynak['url']}

Kategori:
{kaynak.get('kategori','')}

"""
        )



def ilan_taramasi():


    console.print(
        Panel(
            "İLAN TARAMA MOTORU BAŞLADI",
            border_style="yellow"
        )
    )


    kelime = input(
        "Arama kelimesi: "
    )


    url = arama_url_olustur(
        kelime
    )


    sonuc = ilanlari_tara_ve_kaydet(
        url,
        "Sahibinden"
    )


    console.print(
        Panel(
            f"""
Tarama tamamlandı.

Bulunan ilan:
{sonuc}

Veritabanına kaydedildi.
""",
            border_style="green"
        )
    )



def main():

    while True:

        baslik()

        menu()


        secim = input(
            "\nSeçim: "
        )


        if secim == "1":

            kaynaklari_goster()


        elif secim == "2":

            console.print(sistem_durumu())



        elif secim == "3":

            ilan_taramasi()



        elif secim == "4":

            console.print(
                "KantinRadarAI kapatıldı."
            )

            break


        else:

            console.print(
                "Geçersiz seçim"
            )



        input(
            "\nDevam etmek için ENTER..."
        )



if __name__ == "__main__":

    main()
