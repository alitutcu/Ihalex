"""İhalex Türkiye ilçe bazlı ihale yoğunluk haritası."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from harita_motoru import IL_ADLARI, IL_KODLARI, ilce_harita_id, metin_anahtari

GEOJSON_DOSYA = Path(__file__).resolve().parent / "veri" / "harita" / "turkiye_ilceler.geojson"
IL_GEOJSON_DOSYA = Path(__file__).resolve().parent / "veri" / "harita" / "turkiye_il_sinirlari.geojson"
HARITA_YUKSEKLIGI = 680
IL_HARITA_YUKSEKLIGI = 450


def _ilce_adi(ham_ad: str) -> str:
    if "_" in ham_ad:
        return "Merkez"
    return {"Eyüp": "Eyüpsultan"}.get(ham_ad, ham_ad)


def _d3_halqa_yonu(geometri: dict) -> None:
    """ArcGIS/GeoJSON halka yönünü Plotly'nin d3-geo beklentisine çevirir."""
    if geometri.get("type") == "Polygon":
        geometri["coordinates"] = [halka[::-1] for halka in geometri["coordinates"]]
    elif geometri.get("type") == "MultiPolygon":
        geometri["coordinates"] = [
            [halka[::-1] for halka in poligon]
            for poligon in geometri["coordinates"]
        ]


def ilce_secenekleri(il: str) -> list[str]:
    il_kodu = IL_KODLARI.get(il)
    if not il_kodu:
        return []
    with GEOJSON_DOSYA.open("r", encoding="utf-8") as dosya:
        geojson = json.load(dosya)
    return sorted(
        {
            _ilce_adi(str(feature["properties"]["ADI"]))
            for feature in geojson["features"]
            if int(feature["properties"]["IL_ID"]) == il_kodu
        }
    )


def _koordinat_sinirlari(
    features: list[dict],
    boylam_pay_orani: float = 0.08,
    enlem_pay_orani: float = 0.10,
    asgari_pay: float = 0.12,
) -> tuple[list[float], list[float]]:
    boylamlar: list[float] = []
    enlemler: list[float] = []

    def tara(deger: object) -> None:
        if (
            isinstance(deger, list)
            and len(deger) >= 2
            and isinstance(deger[0], (int, float))
            and isinstance(deger[1], (int, float))
        ):
            boylamlar.append(float(deger[0]))
            enlemler.append(float(deger[1]))
        elif isinstance(deger, list):
            for alt in deger:
                tara(alt)

    for feature in features:
        tara(feature["geometry"]["coordinates"])
    if not boylamlar:
        return [25.4, 45.1], [35.5, 42.4]
    boylam_pay = max(
        (max(boylamlar) - min(boylamlar)) * boylam_pay_orani, asgari_pay
    )
    enlem_pay = max(
        (max(enlemler) - min(enlemler)) * enlem_pay_orani, asgari_pay
    )
    return (
        [min(boylamlar) - boylam_pay, max(boylamlar) + boylam_pay],
        [min(enlemler) - enlem_pay, max(enlemler) + enlem_pay],
    )


def turkiye_haritasi(
    df: pd.DataFrame, il: str | None = None, ilce: str | None = None
) -> go.Figure:
    with GEOJSON_DOSYA.open("r", encoding="utf-8") as dosya:
        geojson = json.load(dosya)
    with IL_GEOJSON_DOSYA.open("r", encoding="utf-8") as dosya:
        il_geojson = json.load(dosya)

    il_kodu = IL_KODLARI.get(il or "")
    if il_kodu:
        geojson["features"] = [
            feature for feature in geojson["features"]
            if int(feature["properties"]["IL_ID"]) == il_kodu
        ]
        il_geojson["features"] = [
            feature for feature in il_geojson["features"]
            if metin_anahtari(feature["properties"]["ADI"]) == metin_anahtari(il or "")
        ]
    if il_kodu and ilce:
        secilen_id = ilce_harita_id(il_kodu, ilce)
        geojson["features"] = [
            feature for feature in geojson["features"]
            if ilce_harita_id(
                il_kodu, _ilce_adi(str(feature["properties"]["ADI"]))
            ) == secilen_id
        ]

    for feature in geojson["features"]:
        _d3_halqa_yonu(feature["geometry"])
        ozellikler = feature["properties"]
        il_kodu = int(ozellikler["IL_ID"])
        ilce = _ilce_adi(str(ozellikler["ADI"]))
        ozellikler["harita_id"] = ilce_harita_id(il_kodu, ilce)
        ozellikler["ilce"] = ilce
        ozellikler["il"] = IL_ADLARI[il_kodu] if 0 < il_kodu < len(IL_ADLARI) else ""

    for feature in il_geojson["features"]:
        _d3_halqa_yonu(feature["geometry"])
        feature["properties"]["harita_id"] = str(feature["properties"]["OBJECTID"])

    sayilar = dict(zip(df["harita_id"], df["ilan_sayisi"]))
    satirlar = []
    for feature in geojson["features"]:
        ozellikler = feature["properties"]
        ilan = int(sayilar.get(ozellikler["harita_id"], 0))
        seviye = 0 if ilan == 0 else 1 if ilan == 1 else 2 if ilan <= 5 else 3 if ilan <= 10 else 4
        satirlar.append({
            "harita_id": ozellikler["harita_id"],
            "il": ozellikler["il"],
            "ilce": ozellikler["ilce"],
            "ilan": ilan,
            "seviye": seviye,
        })

    harita_df = pd.DataFrame(satirlar)
    ozel_veri = harita_df[["il", "ilce", "ilan"]].to_numpy()
    ilce_katmani = go.Choropleth(
        geojson=geojson,
        locations=harita_df["harita_id"],
        z=harita_df["seviye"],
        featureidkey="properties.harita_id",
        zmin=0,
        zmax=4,
        colorscale=[
            [0.00, "#d9d9d9"], [0.19, "#d9d9d9"],
            [0.20, "#fff176"], [0.39, "#fff176"],
            [0.40, "#ffd21f"], [0.59, "#ffd21f"],
            [0.60, "#ff8f00"], [0.79, "#ff8f00"],
            [0.80, "#d71920"], [1.00, "#d71920"],
        ],
        marker_line_color="#111111",
        marker_line_width=0.25,
        customdata=ozel_veri,
        hovertemplate=(
            "<b>%{customdata[1]}</b><br>"
            "%{customdata[0]}<br>"
            "İhale: %{customdata[2]}<extra></extra>"
        ),
        colorbar={
            "title": "İhale",
            "tickvals": [0, 1, 2, 3, 4],
            "ticktext": ["0", "1", "2–5", "6–10", "11+"],
        },
    )
    il_katmani = go.Choropleth(
        geojson=il_geojson,
        locations=[str(x["properties"]["OBJECTID"]) for x in il_geojson["features"]],
        z=[0] * len(il_geojson["features"]),
        featureidkey="properties.harita_id",
        zmin=0,
        zmax=1,
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
        marker_line_color="#111111",
        marker_line_width=1.7,
        showscale=False,
        hoverinfo="skip",
    )
    fig = go.Figure(data=[ilce_katmani, il_katmani])
    boylam_araligi, enlem_araligi = _koordinat_sinirlari(geojson["features"])
    odak_merkezi = {
        "lat": sum(enlem_araligi) / 2,
        "lon": sum(boylam_araligi) / 2,
    }
    odak_anahtari = "-".join(
        [
            "ihalex-harita",
            metin_anahtari(il or "turkiye"),
            metin_anahtari(ilce or "tum-ilceler"),
        ]
    )
    fig.update_geos(
        projection_type="mercator",
        center=odak_merkezi,
        lonaxis_range=boylam_araligi,
        lataxis_range=enlem_araligi,
        visible=False,
    )
    fig.update_layout(
        autosize=True,
        height=HARITA_YUKSEKLIGI,
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        uirevision=odak_anahtari,
    )
    return fig


def turkiye_il_haritasi(df: pd.DataFrame) -> go.Figure:
    """Ana sayfa için hızlı, tıklanabilir il yoğunluk haritası üretir."""
    with IL_GEOJSON_DOSYA.open("r", encoding="utf-8") as dosya:
        il_geojson = json.load(dosya)

    for feature in il_geojson["features"]:
        _d3_halqa_yonu(feature["geometry"])
        feature["properties"]["harita_id"] = str(feature["properties"]["ADI"])

    gerekli = ["il", "ilan_sayisi", "aktif_sayisi", "pasif_sayisi", "inceleme_sayisi"]
    hazir = df.copy()
    for sutun in gerekli:
        if sutun not in hazir.columns:
            hazir[sutun] = 0 if sutun != "il" else ""
    ozetler = hazir.set_index("il")[gerekli[1:]].to_dict("index")

    satirlar = []
    for feature in il_geojson["features"]:
        il = str(feature["properties"]["ADI"])
        ozet = ozetler.get(il, {})
        toplam = int(ozet.get("ilan_sayisi", 0))
        seviye = 0 if toplam == 0 else 1 if toplam == 1 else 2 if toplam <= 5 else 3 if toplam <= 10 else 4
        satirlar.append({
            "il": il,
            "ilan_sayisi": toplam,
            "aktif_sayisi": int(ozet.get("aktif_sayisi", 0)),
            "pasif_sayisi": int(ozet.get("pasif_sayisi", 0)),
            "inceleme_sayisi": int(ozet.get("inceleme_sayisi", 0)),
            "seviye": seviye,
        })

    harita_df = pd.DataFrame(satirlar)
    ozel_veri = harita_df[
        ["il", "ilan_sayisi", "aktif_sayisi", "pasif_sayisi", "inceleme_sayisi"]
    ].to_numpy()
    katman = go.Choropleth(
        geojson=il_geojson,
        locations=harita_df["il"],
        z=harita_df["seviye"],
        featureidkey="properties.harita_id",
        zmin=0,
        zmax=4,
        colorscale=[
            [0.00, "#D9D9D9"], [0.19, "#D9D9D9"],
            [0.20, "#FFF2B5"], [0.39, "#FFF2B5"],
            [0.40, "#FFE990"], [0.59, "#FFE990"],
            [0.60, "#FFE063"], [0.79, "#FFE063"],
            [0.80, "#FFD21F"], [1.00, "#FFD21F"],
        ],
        marker_line_color="#FFFFFF",
        marker_line_width=1.05,
        customdata=ozel_veri,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Toplam ihale: %{customdata[1]}<br>"
            "Aktif: %{customdata[2]} · Geçmiş: %{customdata[3]}<br>"
            "İncelemede: %{customdata[4]}"
            "<extra>İlanları açmak için tıklayın</extra>"
        ),
        showscale=False,
    )
    fig = go.Figure(data=[katman])
    boylam_araligi, enlem_araligi = _koordinat_sinirlari(
        il_geojson["features"],
        boylam_pay_orani=0.025,
        enlem_pay_orani=0.035,
        asgari_pay=0.05,
    )
    odak_merkezi = {
        "lat": sum(enlem_araligi) / 2,
        "lon": sum(boylam_araligi) / 2,
    }
    fig.update_geos(
        projection_type="mercator",
        center=odak_merkezi,
        lonaxis_range=boylam_araligi,
        lataxis_range=enlem_araligi,
        domain={"x": [0, 1], "y": [0, 1]},
        visible=False,
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        autosize=True,
        height=IL_HARITA_YUKSEKLIGI,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="#111111",
        plot_bgcolor="#111111",
        clickmode="event+select",
        dragmode=False,
        uirevision="ihalex-ana-sayfa-il-haritasi",
    )
    return fig
