import os
import json
from rich.table import Table
from rich.panel import Panel
from rich.console import Console


console = Console()


def sistem_durumu():

    # Kaynak haritası kontrolü
    try:
        with open(
            "kaynak_haritasi.json",
            "r",
            encoding="utf-8"
        ) as dosya:

            harita = json.load(dosya)

        kaynak_sayisi = 0
        il_sayisi = 0
        ilce_sayisi = 0


        iller = harita.get("Turkiye", {})

        il_sayisi = len(iller)


        for ilceler in iller.values():

            ilce_sayisi += len(ilceler)


            for ilce in ilceler.values():

                kaynaklar = ilce.get(
                    "kaynaklar",
                    []
                )

                kaynak_sayisi += len(kaynaklar)



    except Exception:

        il_sayisi = 0
        ilce_sayisi = 0
        kaynak_sayisi = 0



    # Dashboard tablosu

    tablo = Table(
        title="KANTİN RADAR AI - SİSTEM DURUMU"
    )


    tablo.add_column(
        "Modül",
        style="cyan"
    )

    tablo.add_column(
        "Durum",
        style="green"
    )

    tablo.add_column(
        "Bilgi"
    )


    tablo.add_row(
        "Kaynak Haritası",
        "AKTİF",
        f"{il_sayisi} il / {ilce_sayisi} ilçe"
    )


    tablo.add_row(
        "İlan Kaynakları",
        "AKTİF",
        f"{kaynak_sayisi} kaynak"
    )


    tablo.add_row(
        "Tarama Motoru",
        "HAZIR",
        "Beklemede"
    )


    tablo.add_row(
        "Analiz Motoru",
        "HAZIR",
        "Kantin Skoru"
    )


    return tablo
