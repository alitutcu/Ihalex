"""İhalex'in hızlı, mobil uyumlu ve WebView içinde çalışabilen web arayüzü."""

from __future__ import annotations

import base64
from datetime import date, datetime
import html
import hmac
import logging
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from harita_gosterici import ilce_secenekleri, turkiye_haritasi, turkiye_il_haritasi
from harita_motoru import IL_ADLARI, ilce_harita_istatistikleri
from istatistik_motoru import tekrar_ihale_ozeti
from meb_kaynaklari import kaynak_ozeti
from telegram_alarm import (
    TelegramKurulumHatasi,
    aktif_ilanlari_kuyruga_al,
    alarm_ozeti,
    bekleyenleri_gonder,
    telegram_abone_listesi,
    telegram_abone_ozeti,
    telegram_aboneleri_yenile,
    telegram_baglantisini_kur,
    telegram_bot_baglantisi,
    telegram_hazir,
    telegram_test_mesaji_gonder,
)
from veritabani import DB, ham_arsiv_ozeti, ihale_tarih_siniri


st.set_page_config(
    page_title="İhalex — Türkiye'nin İhale Fırsat Haritası",
    page_icon="📣",
    layout="wide",
    initial_sidebar_state="collapsed",
)


SAYFALAR = {
    "Ana Sayfa": "ana-sayfa",
    "İhaleler": "ihaleler",
    "Harita": "harita",
    "İstatistikler": "istatistikler",
    "Yönetim": "yonetim",
}
SAYFA_ADLARI = {deger: anahtar for anahtar, deger in SAYFALAR.items()}
BANNER_GORSELI = Path(__file__).resolve().parent / "assets" / "banner-school-cafeteria-source.jpg"


@st.cache_data(show_spinner=False)
def gorsel_data_uri(dosya: str) -> str:
    yol = Path(dosya)
    if not yol.is_file():
        return ""
    kod = base64.b64encode(yol.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{kod}"


def stilleri_yukle(gomulu: bool) -> None:
    gomulu_css = """
        [data-testid="stHeader"] { display: none; }
        .block-container { padding-top: .6rem !important; }
        .ihalex-radar-banner { display: none !important; }
    """ if gomulu else ""
    st.markdown(
        f"""
        <style>
        :root {{
            --ihalex-yellow: #FFD21F;
            --ihalex-red: #D71920;
            --ihalex-black: #111111;
            --ihalex-paper: #f7f7f2;
        }}
        .stApp {{ background: var(--ihalex-paper); color: var(--ihalex-black); }}
        .block-container {{
            max-width: 1240px;
            padding: 1rem 1.4rem 4rem;
        }}
        [data-testid="stHeader"] {{ background: rgba(247,247,242,.94); }}
        #MainMenu, footer, .stAppDeployButton {{ display: none !important; }}
        .ihalex-radar-banner {{
            position: relative;
            isolation: isolate;
            display: grid;
            grid-template-columns: minmax(310px, 1.35fr) minmax(250px, 1fr) 116px;
            align-items: center;
            min-height: 138px;
            height: clamp(138px, 11.5vw, 152px);
            background: var(--ihalex-yellow);
            border: 2px solid var(--ihalex-black);
            border-radius: 16px;
            overflow: hidden;
            margin: .25rem 0 1rem;
            box-shadow: 0 7px 0 var(--ihalex-black);
        }}
        .ihalex-radar-banner::after {{
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            height: 7px;
            background: var(--ihalex-red);
            z-index: 5;
        }}
        .ihalex-radar-photo {{
            position: absolute;
            inset: 0 0 0 36%;
            z-index: -2;
            background-image: var(--ihalex-banner-photo);
            background-position: center 54%;
            background-size: cover;
            filter: grayscale(1) contrast(1.25);
            opacity: .55;
        }}
        .ihalex-radar-photo::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: var(--ihalex-yellow);
            mix-blend-mode: multiply;
            opacity: .72;
        }}
        .ihalex-radar-brand {{
            display: flex;
            align-items: center;
            gap: clamp(.75rem, 1.4vw, 1.2rem);
            min-width: 0;
            padding: 1rem clamp(1.25rem, 3vw, 2.7rem);
        }}
        .ihalex-radar-brand h1 {{
            margin: 0;
            font-family: "Arial Rounded MT Bold", "Arial Black", Arial, sans-serif;
            font-size: clamp(2.65rem, 5vw, 4.6rem);
            font-weight: 900;
            line-height: .84;
            letter-spacing: -.085em;
            color: var(--ihalex-black);
            white-space: nowrap;
        }}
        .ihalex-radar-brand .x {{ color: var(--ihalex-red); }}
        .ihalex-human-i {{
            position: relative;
            flex: 0 0 auto;
            width: clamp(25px, 2.6vw, 34px);
            height: clamp(49px, 5.2vw, 66px);
            margin-top: .55rem;
            border-radius: 14px 14px 7px 7px;
            background: var(--ihalex-black);
        }}
        .ihalex-human-i::before {{
            content: "";
            position: absolute;
            width: 68%;
            aspect-ratio: 1;
            left: 16%;
            top: -42%;
            border: 3px solid var(--ihalex-black);
            border-radius: 50%;
            background: var(--ihalex-red);
        }}
        .ihalex-human-i::after {{
            content: "";
            position: absolute;
            width: 176%;
            height: 13%;
            left: -38%;
            top: 20%;
            border-radius: 999px;
            background: var(--ihalex-black);
            transform: rotate(-5deg);
        }}
        .ihalex-radar-copy {{
            position: relative;
            min-width: 0;
            padding: .4rem 1rem .4rem 1.25rem;
            border-left: 5px solid var(--ihalex-red);
        }}
        .ihalex-radar-copy small {{
            display: block;
            margin-bottom: .25rem;
            font-size: .7rem;
            font-weight: 900;
            letter-spacing: .14em;
            text-transform: uppercase;
        }}
        .ihalex-radar-copy strong {{
            display: block;
            max-width: 300px;
            font-size: clamp(1.15rem, 2vw, 1.65rem);
            line-height: 1.04;
        }}
        .ihalex-radar-signal {{
            position: relative;
            display: grid;
            place-items: center;
            width: 100px;
            height: 100px;
            border: 2px solid var(--ihalex-black);
            border-radius: 50%;
            background: rgba(255,210,31,.88);
        }}
        .ihalex-radar-signal::before,
        .ihalex-radar-signal::after {{
            content: "";
            position: absolute;
            border: 1px solid var(--ihalex-black);
            border-radius: 50%;
        }}
        .ihalex-radar-signal::before {{ inset: 14px; }}
        .ihalex-radar-signal::after {{ inset: 29px; }}
        .ihalex-radar-sweep {{
            position: absolute;
            inset: 5px 50% 50% 5px;
            border-radius: 100% 0 0;
            background: var(--ihalex-red);
            clip-path: polygon(100% 100%, 0 100%, 100% 0);
            transform-origin: 100% 100%;
            animation: ihalex-radar-don 4s linear infinite;
            opacity: .82;
        }}
        .ihalex-radar-signal span {{
            position: relative;
            z-index: 2;
            display: grid;
            place-items: center;
            width: 54px;
            height: 54px;
            border-radius: 50%;
            background: var(--ihalex-black);
            color: var(--ihalex-yellow);
            font-size: .62rem;
            font-weight: 900;
            line-height: 1.15;
            text-align: center;
        }}
        @keyframes ihalex-radar-don {{ to {{ transform: rotate(360deg); }} }}
        @media (prefers-reduced-motion: reduce) {{
            .ihalex-radar-sweep {{ animation: none; }}
        }}
        .ihalex-portal-band {{
            background: #171717;
            color: white;
            border-left: 6px solid var(--ihalex-red);
            border-radius: 8px;
            padding: .72rem 1rem;
            margin: .25rem 0 1rem;
            font-size: .88rem;
            font-weight: 750;
        }}
        .ihalex-category-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .75rem;
            margin: 1rem 0 1.5rem;
        }}
        .ihalex-category-card {{
            display: block;
            background: white;
            border: 1px solid #d8d8d0;
            border-top: 5px solid var(--ihalex-yellow);
            border-radius: 8px;
            padding: 1rem;
            color: var(--ihalex-black) !important;
            text-decoration: none !important;
            box-shadow: 0 3px 12px rgba(17,17,17,.05);
            transition: transform .15s ease, border-color .15s ease;
        }}
        .ihalex-category-card:hover {{
            transform: translateY(-2px);
            border-color: var(--ihalex-red);
        }}
        .ihalex-category-card strong {{
            display: block;
            font-size: 1.55rem;
            line-height: 1;
            margin-bottom: .45rem;
        }}
        .ihalex-category-card span {{
            color: #5c5c56;
            font-size: .78rem;
            font-weight: 800;
            letter-spacing: .035em;
        }}
        .ihalex-section-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            border-bottom: 2px solid #222;
            margin: 1.5rem 0 1rem;
            padding-bottom: .55rem;
        }}
        .ihalex-section-head h3 {{ margin: 0; font-size: 1.25rem; }}
        .ihalex-section-head a {{
            color: var(--ihalex-red) !important;
            font-size: .82rem;
            font-weight: 800;
            text-decoration: none;
        }}
        .ihalex-service-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .8rem;
            margin: 1.4rem 0 .5rem;
        }}
        .st-key-ana_sayfa_harita {{
            background: var(--ihalex-black);
            border: 2px solid var(--ihalex-black);
            border-radius: 12px;
            padding: .6rem;
            overflow: hidden;
            box-shadow: 0 7px 0 var(--ihalex-yellow);
        }}
        .ihalex-service-card {{
            background: #191919;
            color: white;
            border-left: 5px solid var(--ihalex-yellow);
            border-radius: 8px;
            padding: 1rem;
        }}
        .ihalex-service-card b {{ display: block; margin-bottom: .35rem; }}
        .ihalex-service-card small {{ color: #d6d6d0; line-height: 1.45; }}
        .st-key-ana_navigasyon {{
            position: sticky;
            top: .45rem;
            z-index: 999;
            background: rgba(247,247,242,.96);
            border: 1px solid #deded5;
            border-radius: 14px;
            padding: .35rem;
            backdrop-filter: blur(12px);
            margin-bottom: 1.2rem;
        }}
        .st-key-ana_navigasyon [data-baseweb="button-group"] {{ width: 100%; }}
        .st-key-ana_navigasyon button {{ min-height: 42px; font-weight: 750; }}
        [data-testid="stMetric"] {{
            background: white;
            border: 1px solid #dfdfd7;
            border-radius: 16px;
            padding: .9rem 1rem;
            box-shadow: 0 4px 15px rgba(17,17,17,.05);
        }}
        [data-testid="stMetricValue"] {{ color: var(--ihalex-black); }}
        .stButton button, .stLinkButton a, [data-testid="stFormSubmitButton"] button {{
            min-height: 44px;
            border-radius: 12px;
            font-weight: 750;
        }}
        .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {{
            background: var(--ihalex-red);
            border-color: var(--ihalex-red);
        }}
        [data-testid="stDataFrame"] {{
            border: 1px solid #dfdfd7;
            border-radius: 14px;
            overflow: hidden;
            background: white;
        }}
        .st-key-portal_arama {{
            background: white;
            border: 1px solid #d7d7cf;
            border-radius: 12px;
            padding: .8rem 1rem .35rem;
            box-shadow: 0 6px 22px rgba(17,17,17,.07);
            margin-bottom: 1rem;
        }}
        .st-key-ihale_portali > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{
            background: white;
            border: 1px solid #d7d7cf;
            border-top: 4px solid var(--ihalex-red);
            border-radius: 10px;
            padding: .85rem;
            align-self: flex-start;
        }}
        .st-key-ana_sayfa_portal > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{
            background: white;
            border: 1px solid #d7d7cf;
            border-top: 4px solid var(--ihalex-yellow);
            border-radius: 8px;
            padding: .85rem;
            align-self: flex-start;
        }}
        .ihalex-result-header, .ihalex-result-row {{
            display: grid;
            grid-template-columns: 1.35fr 2.35fr .85fr .7fr;
            gap: .75rem;
            align-items: center;
        }}
        .ihalex-result-header {{
            background: #1c1c1c;
            color: white;
            border-radius: 7px 7px 0 0;
            padding: .7rem .85rem;
            font-size: .72rem;
            font-weight: 850;
            letter-spacing: .035em;
        }}
        .ihalex-result-row {{
            background: white;
            color: #151515 !important;
            border: 1px solid #e0e0d8;
            border-top: 0;
            padding: .8rem .85rem;
            text-decoration: none !important;
            transition: background .15s ease;
        }}
        .ihalex-result-row:hover {{ background: #fff9d7; }}
        .ihalex-result-row:last-child {{ border-radius: 0 0 7px 7px; }}
        .ihalex-result-row .kurum {{
            color: #5a5a54;
            font-size: .73rem;
            font-weight: 750;
            text-transform: uppercase;
        }}
        .ihalex-result-row .baslik {{ font-size: .88rem; font-weight: 800; }}
        .ihalex-result-row .tarih, .ihalex-result-row .sehir {{
            color: #4e4e49;
            font-size: .78rem;
            font-weight: 700;
        }}
        .ihalex-card-title {{ font-size: 1rem; font-weight: 800; line-height: 1.35; }}
        .ihalex-card-meta {{ color: #5d5d57; font-size: .82rem; margin-top: .25rem; }}
        .ihalex-mobile-note {{ color: #575750; font-size: .84rem; }}
        .ihalex-footer {{
            border-top: 1px solid #d7d7ce;
            margin-top: 2.5rem;
            padding-top: 1rem;
            color: #65655f;
            font-size: .82rem;
        }}
        @media (max-width: 760px) {{
            .block-container {{ padding: .6rem .72rem 5.5rem; }}
            .ihalex-radar-banner {{
                grid-template-columns: minmax(0, 1fr) 78px;
                height: 132px;
                min-height: 132px;
                border-radius: 13px;
                box-shadow: 0 5px 0 var(--ihalex-black);
            }}
            .ihalex-radar-photo {{ inset: 0 0 0 30%; }}
            .ihalex-radar-brand {{
                align-self: start;
                gap: .55rem;
                padding: 1.1rem .75rem .35rem 1rem;
            }}
            .ihalex-radar-brand h1 {{ font-size: clamp(2rem, 10vw, 2.8rem); }}
            .ihalex-human-i {{ width: 19px; height: 38px; margin-top: .35rem; }}
            .ihalex-human-i::before {{ border-width: 2px; }}
            .ihalex-radar-copy {{
                position: absolute;
                left: 1rem;
                bottom: 16px;
                max-width: calc(100% - 104px);
                padding: .1rem 0 .1rem .65rem;
                border-left-width: 4px;
            }}
            .ihalex-radar-copy small {{ display: none; }}
            .ihalex-radar-copy strong {{ font-size: .82rem; line-height: 1.08; }}
            .ihalex-radar-signal {{
                grid-column: 2;
                grid-row: 1;
                width: 70px;
                height: 70px;
                margin-right: .4rem;
            }}
            .ihalex-radar-signal::before {{ inset: 10px; }}
            .ihalex-radar-signal::after {{ inset: 21px; }}
            .ihalex-radar-signal span {{ width: 40px; height: 40px; font-size: .48rem; }}
            .ihalex-category-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .ihalex-service-grid {{ grid-template-columns: 1fr; }}
            .st-key-ana_navigasyon {{
                position: fixed;
                top: auto;
                bottom: .45rem;
                left: .45rem;
                right: .45rem;
                margin: 0;
                box-shadow: 0 8px 30px rgba(17,17,17,.18);
            }}
            .st-key-ana_navigasyon [data-baseweb="button-group"] {{
                display: grid !important;
                grid-template-columns: repeat(5, minmax(0, 1fr));
            }}
            .st-key-ana_navigasyon button {{
                min-width: 0 !important;
                padding: .45rem .18rem !important;
                font-size: .68rem !important;
            }}
            [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; gap: .55rem; }}
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                min-width: calc(50% - .3rem) !important;
                flex: 1 1 calc(50% - .3rem) !important;
            }}
            .st-key-ihale_filtreleri [data-testid="stColumn"],
            .st-key-harita_filtreleri [data-testid="stColumn"],
            .st-key-ihale_portali [data-testid="stColumn"],
            .st-key-ana_sayfa_portal [data-testid="stColumn"] {{
                min-width: 100% !important;
                flex-basis: 100% !important;
            }}
            .ihalex-result-header {{ display: none; }}
            .ihalex-result-row {{
                grid-template-columns: 1fr;
                gap: .25rem;
                border-top: 1px solid #e0e0d8;
                border-radius: 7px;
                margin-bottom: .55rem;
            }}
            [data-baseweb="select"] > div, input {{ font-size: 16px !important; }}
            .js-plotly-plot, .plot-container {{ min-height: 470px !important; }}
            .st-key-ana_sayfa_harita .js-plotly-plot,
            .st-key-ana_sayfa_harita .plot-container {{ min-height: 360px !important; }}
        }}
        {gomulu_css}
        </style>
        """,
        unsafe_allow_html=True,
    )


def resmi_meb_url(url: str) -> bool:
    host = (urlparse(str(url)).hostname or "").lower()
    return host == "meb.gov.tr" or host.endswith(".meb.gov.tr")


@st.cache_data(ttl=60, show_spinner=False)
def veri_getir() -> pd.DataFrame:
    sorgu = """
        WITH sirali AS (
            SELECT d.baslik, k.il, k.ilce, k.kurum_adi AS kaynak,
                   d.yayin_tarihi, d.ihale_tarihi, d.durum,
                   COALESCE(NULLIF(d.detay_url, ''), d.url) AS ihale_url,
                   d.ilk_gorulme,
                   ROW_NUMBER() OVER (
                       PARTITION BY COALESCE(NULLIF(d.detay_url, ''), d.url)
                       ORDER BY CASE d.eslesme_turu
                           WHEN 'detay' THEN 0 WHEN 'toplu_dosya' THEN 1
                           WHEN 'dosya' THEN 2 ELSE 3 END, d.id
                   ) AS sira
            FROM duyuru_adaylari d
            JOIN kaynaklar k ON k.id=d.kaynak_id
            WHERE d.yayin_tarihi >= ?
        )
        SELECT baslik, il, ilce, kaynak, yayin_tarihi, ihale_tarihi,
               durum, ihale_url, ilk_gorulme
        FROM sirali WHERE sira=1
        ORDER BY yayin_tarihi DESC, ilk_gorulme DESC
    """
    try:
        with sqlite3.connect(DB) as conn:
            df = pd.read_sql_query(
                sorgu, conn, params=(ihale_tarih_siniri().isoformat(),)
            )
    except (sqlite3.Error, pd.errors.DatabaseError):
        logging.exception("İhale verisi okunamadı")
        return pd.DataFrame()
    if df.empty:
        return df
    df["yayin_tarihi"] = pd.to_datetime(df["yayin_tarihi"], errors="coerce")
    df["ihale_tarihi"] = pd.to_datetime(df["ihale_tarihi"], errors="coerce")
    df = df.dropna(subset=["yayin_tarihi"])
    df["ilce"] = df["ilce"].fillna("")
    df["gun"] = (pd.Timestamp(date.today()) - df["yayin_tarihi"]).dt.days.clip(lower=0)
    df["durum_etiketi"] = df["durum"].map({
        "aktif": "🟢 Aktif",
        "pasif": "⚫ Pasif",
        "tarih_bekleniyor": "🟡 Doğrulanıyor",
    }).fillna("🟡 Doğrulanıyor")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def harita_verisi_getir() -> pd.DataFrame:
    return ilce_harita_istatistikleri()


def tablo_goster(veri: pd.DataFrame) -> None:
    if veri.empty:
        st.info("Bu filtrelerle eşleşen ihale bulunamadı.")
        return
    gorunum = veri.rename(columns={
        "baslik": "İhale", "il": "İl", "ilce": "İlçe", "kaynak": "MEB kaynağı",
        "yayin_tarihi": "Yayın tarihi", "ihale_tarihi": "İhale tarihi",
        "durum_etiketi": "Durum", "ihale_url": "Bağlantı",
    }).copy()
    gorunum["İlçe"] = gorunum["İlçe"].replace("", "Doğrulanıyor")
    gorunum.loc[
        ~gorunum["Bağlantı"].map(resmi_meb_url), "Bağlantı"
    ] = ""
    st.dataframe(
        gorunum[[
            "İhale", "İl", "İlçe", "Yayın tarihi", "İhale tarihi",
            "Durum", "MEB kaynağı", "Bağlantı",
        ]],
        width="stretch",
        hide_index=True,
        column_config={
            "Yayın tarihi": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "İhale tarihi": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "Bağlantı": st.column_config.LinkColumn(display_text="Resmî ilanı aç"),
        },
    )


def kartlar_goster(veri: pd.DataFrame) -> None:
    if veri.empty:
        st.info("Bu filtrelerle eşleşen ihale bulunamadı.")
        return
    for _, satir in veri.iterrows():
        with st.container(border=True):
            baslik = html.escape(str(satir["baslik"] or "Kantin ihalesi"))
            ilce = str(satir["ilce"] or "İlçe doğrulanıyor")
            st.html(
                f"<div class='ihalex-card-title'>{baslik}</div>"
                f"<div class='ihalex-card-meta'>{html.escape(str(satir['il']))} · "
                f"{html.escape(ilce)} · {html.escape(str(satir['kaynak']))}</div>"
            )
            c1, c2, c3 = st.columns(3)
            c1.caption(f"Yayın: {satir['yayin_tarihi'].strftime('%d.%m.%Y')}")
            ihale_tarihi = satir["ihale_tarihi"]
            c2.caption(
                "İhale: " + (
                    ihale_tarihi.strftime("%d.%m.%Y")
                    if pd.notna(ihale_tarihi) else "Doğrulanıyor"
                )
            )
            c3.caption(str(satir["durum_etiketi"]))
            if resmi_meb_url(str(satir["ihale_url"])):
                st.link_button("Resmî ilanı aç", str(satir["ihale_url"]), width="stretch")


def vitrin_kartlari_goster(veri: pd.DataFrame) -> None:
    """Ana sayfadaki öne çıkan ilanları portal kartlarıyla gösterir."""
    if veri.empty:
        st.info("Şu anda öne çıkarılacak aktif ihale bulunmuyor.")
        return
    kolonlar = st.columns(3)
    for sira, (_, satir) in enumerate(veri.head(6).iterrows()):
        with kolonlar[sira % 3]:
            with st.container(border=True):
                st.html(
                    "<div class='ihalex-card-title'>"
                    + html.escape(str(satir["baslik"] or "Kantin ihalesi"))
                    + "</div><div class='ihalex-card-meta'>"
                    + html.escape(str(satir["il"])) + " · "
                    + html.escape(str(satir["ilce"] or "İlçe doğrulanıyor"))
                    + "</div>"
                )
                tarih = satir["ihale_tarihi"]
                if pd.notna(tarih):
                    st.caption(f"İhale tarihi · {tarih.strftime('%d.%m.%Y')}")
                else:
                    st.caption("İhale tarihi doğrulanıyor")
                if resmi_meb_url(str(satir["ihale_url"])):
                    st.link_button(
                        "İlanı incele", str(satir["ihale_url"]), width="stretch"
                    )


def portal_satirlari_goster(veri: pd.DataFrame) -> None:
    """İlan.gov.tr benzeri kurum–başlık–tarih–şehir sonuç satırları."""
    if veri.empty:
        st.info("Seçilen filtrelerle eşleşen ilan bulunamadı.")
        return
    parcalar = [
        "<div class='ihalex-result-header'><span>MEB KAYNAĞI</span>"
        "<span>İLAN BAŞLIĞI</span><span>İHALE TARİHİ</span><span>ŞEHİR</span></div>"
    ]
    for _, satir in veri.iterrows():
        url = str(satir["ihale_url"])
        if not resmi_meb_url(url):
            continue
        tarih = satir["ihale_tarihi"]
        tarih_metni = tarih.strftime("%d.%m.%Y") if pd.notna(tarih) else "İnceleniyor"
        parcalar.append(
            "<a class='ihalex-result-row' target='_blank' rel='noopener noreferrer' href='"
            + html.escape(url, quote=True) + "'>"
            + "<span class='kurum'>" + html.escape(str(satir["kaynak"])) + "</span>"
            + "<span class='baslik'>" + html.escape(str(satir["baslik"])) + "</span>"
            + "<span class='tarih'>" + html.escape(tarih_metni) + "</span>"
            + "<span class='sehir'>" + html.escape(str(satir["il"])) + "</span></a>"
        )
    st.markdown("".join(parcalar), unsafe_allow_html=True)


def ana_sayfa_filtreleri_goster(df: pd.DataFrame) -> None:
    """Ana sayfada görünür gelişmiş filtre ve ilan sonuçlarını gösterir."""
    st.markdown(
        "<div class='ihalex-section-head'><h3>Kantin İhale İlanları</h3>"
        "<a href='?sayfa=ihaleler'>GELİŞMİŞ İLAN SAYFASI →</a></div>",
        unsafe_allow_html=True,
    )
    with st.container(key="ana_sayfa_portal"):
        filtre_sutunu, sonuc_sutunu = st.columns([1, 3])
        with filtre_sutunu:
            st.markdown("#### Filtrele")
            kelime = st.text_input(
                "Kelime ile arayınız", placeholder="Okul veya ihale adı",
                key="ana_filtre_kelime",
            )
            il = st.selectbox(
                "İlan yeri", ["Tüm Türkiye"] + sorted(df["il"].dropna().unique()),
                key="ana_filtre_il",
            )
            ilceler = sorted(
                df.loc[df["il"] == il, "ilce"].replace("", pd.NA).dropna().unique()
            )
            ilce = st.selectbox(
                "İlçe", ["Tüm ilçeler"] + ilceler,
                disabled=il == "Tüm Türkiye", key="ana_filtre_ilce",
            )
            kaynaklar = sorted(df["kaynak"].dropna().unique())
            kaynak = st.selectbox(
                "Kuruma göre arama", ["Tüm MEB kaynakları"] + kaynaklar,
                key="ana_filtre_kaynak",
            )
            durum = st.selectbox(
                "İlan durumu", ["Tümü", "Aktif", "Pasif", "Tarih incelemede"],
                key="ana_filtre_durum",
            )
            ilk_tarih = st.date_input(
                "İlk yayın tarihi", value=ihale_tarih_siniri(),
                min_value=ihale_tarih_siniri(), max_value=date.today(),
                key="ana_filtre_ilk_tarih",
            )
            son_tarih = st.date_input(
                "Son yayın tarihi", value=date.today(),
                min_value=ihale_tarih_siniri(), max_value=date.today(),
                key="ana_filtre_son_tarih",
            )
            st.button("İLAN ARA", type="primary", width="stretch", key="ana_filtre_ara")
        filtre = df[
            (df["yayin_tarihi"].dt.date >= ilk_tarih)
            & (df["yayin_tarihi"].dt.date <= son_tarih)
        ]
        if kelime:
            arama_alani = filtre["baslik"].fillna("") + " " + filtre["kaynak"].fillna("")
            filtre = filtre[arama_alani.str.contains(kelime, case=False, regex=False)]
        if il != "Tüm Türkiye":
            filtre = filtre[filtre["il"] == il]
        if ilce != "Tüm ilçeler":
            filtre = filtre[filtre["ilce"] == ilce]
        if kaynak != "Tüm MEB kaynakları":
            filtre = filtre[filtre["kaynak"] == kaynak]
        durum_kodu = {
            "Aktif": "aktif", "Pasif": "pasif", "Tarih incelemede": "tarih_bekleniyor"
        }
        if durum in durum_kodu:
            filtre = filtre[filtre["durum"] == durum_kodu[durum]]
        with sonuc_sutunu:
            r1, r2 = st.columns([2, 1])
            siralama = r1.selectbox(
                "Sıralama", ["En yeni yayın", "En yakın ihale tarihi", "Okul adına göre"],
                key="ana_filtre_siralama",
            )
            gorunum = r2.segmented_control(
                "Görünüm", ["Liste", "Kart"], default="Liste", key="ana_filtre_gorunum"
            )
            if siralama == "En yakın ihale tarihi":
                filtre = filtre.sort_values("ihale_tarihi", na_position="last")
            elif siralama == "Okul adına göre":
                filtre = filtre.sort_values("baslik")
            else:
                filtre = filtre.sort_values("yayin_tarihi", ascending=False)
            st.caption(f"Toplam {len(filtre)} ilan · İlk 12 sonuç gösteriliyor")
            parca = filtre.head(12)
            if gorunum == "Kart":
                kartlar_goster(parca)
            else:
                portal_satirlari_goster(parca)


def ana_sayfa_haritasi_goster(df: pd.DataFrame) -> None:
    """İlan.gov.tr kullanım akışına benzeyen tıklanabilir il haritasını gösterir."""
    harita_kayitlari = df.copy()
    harita_kayitlari["il"] = harita_kayitlari["il"].replace(
        {"Afyon": "Afyonkarahisar"}
    )
    ozet = (
        harita_kayitlari.groupby("il", as_index=False)
        .agg(
            ilan_sayisi=("durum", "size"),
            aktif_sayisi=("durum", lambda seri: int((seri == "aktif").sum())),
            pasif_sayisi=("durum", lambda seri: int((seri == "pasif").sum())),
            inceleme_sayisi=(
                "durum", lambda seri: int((seri == "tarih_bekleniyor").sum())
            ),
        )
    )
    st.markdown(
        "<div class='ihalex-section-head'><h3>İlan Haritası</h3>"
        "<a href='?sayfa=harita'>İLÇE HARİTASINI AÇ →</a></div>",
        unsafe_allow_html=True,
    )
    with st.container(key="ana_sayfa_harita"):
        figur = turkiye_il_haritasi(ozet)
        secim = st.plotly_chart(
            figur,
            width="stretch",
            key="ana_sayfa_turkiye_il_haritasi",
            on_select="rerun",
            selection_mode="points",
            config={
                "responsive": True,
                "scrollZoom": False,
                "displayModeBar": False,
                "displaylogo": False,
            },
        )
    st.caption("Bir ilin kantin ihale ilanlarını görmek için haritada o ile tıklayın.")
    noktalar = (getattr(secim, "selection", {}) or {}).get("points", [])
    if noktalar:
        nokta = noktalar[0]
        il = str(nokta.get("location") or "")
        if not il:
            ozel = nokta.get("customdata") or []
            il = str(ozel[0]) if ozel else ""
        if il in IL_ADLARI:
            il = {"Afyonkarahisar": "Afyon"}.get(il, il)
            st.query_params["sayfa"] = "ihaleler"
            st.query_params["il"] = il
            st.rerun()


def ozet_kartlari(df: pd.DataFrame) -> None:
    toplam = len(df)
    aktif = int((df["durum"] == "aktif").sum()) if not df.empty else 0
    pasif = int((df["durum"] == "pasif").sum()) if not df.empty else 0
    bekleyen = int((df["durum"] == "tarih_bekleniyor").sum()) if not df.empty else 0
    sutunlar = st.columns(4)
    for sutun, baslik, deger in zip(
        sutunlar,
        ("Toplam İhale", "Aktif İhale", "Geçmiş İhale", "Tarih İncelemede"),
        (toplam, aktif, pasif, bekleyen),
    ):
        sutun.metric(baslik, deger)


def kaynak_kapsami_goster() -> None:
    kaynaklar = kaynak_ozeti()
    ham_arsiv = ham_arsiv_ozeti()
    taranan = int(kaynaklar["basarili"]) + int(kaynaklar["hata"])
    toplam = max(int(kaynaklar["dogrulanmis"]), taranan, 1)
    st.subheader("Türkiye MEB Kaynak Kapsamı")
    st.progress(
        min(taranan / toplam, 1.0),
        text=f"{taranan}/{toplam} resmî MEB kaynağı kontrol edildi",
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("İl kaynağı", kaynaklar["il"])
    k2.metric("İlçe kaynağı", kaynaklar["ilce"])
    k3.metric("Başarılı", kaynaklar["basarili"])
    k4.metric("Hatalı", kaynaklar["hata"])
    st.caption(
        f"Son 1 yıllık ham arşiv: {ham_arsiv['toplam']} bağlantı · "
        f"Doğrulandı: {ham_arsiv['dogrulandi']} · "
        f"Yeniden denenecek: {ham_arsiv['bekliyor']} · "
        "Tam tarama her gün 11:59 ve 23:59'da."
    )


def ana_sayfa(df: pd.DataFrame) -> None:
    st.markdown(
        "<div class='ihalex-portal-band'>MEB KANTİN İHALELERİ · TÜM TÜRKİYE · "
        "İL VE İLÇE BAZLI RESMÎ DUYURULAR · BAĞIMSIZ TAKİP PLATFORMU</div>",
        unsafe_allow_html=True,
    )
    with st.container(key="portal_arama"):
        with st.form("ana_sayfa_arama_formu", border=False):
            arama_sutunu, dugme_sutunu = st.columns([5, 1])
            arama = arama_sutunu.text_input(
                "Kelime ya da okul adı ile arayınız",
                placeholder="Örnek: Tüpraş İlkokulu, Manavgat veya kantin ihalesi",
                key="ana_sayfa_arama",
            ).strip()
            dugme_sutunu.form_submit_button(
                "İLAN ARA", type="primary", width="stretch"
            )
    toplam = len(df)
    aktif = int((df["durum"] == "aktif").sum())
    pasif = int((df["durum"] == "pasif").sum())
    bekleyen = int((df["durum"] == "tarih_bekleniyor").sum())
    st.markdown(
        f"""
        <div class="ihalex-category-grid">
          <a class="ihalex-category-card" href="?sayfa=ihaleler">
            <strong>{toplam}</strong><span>TÜM İLANLAR</span>
          </a>
          <a class="ihalex-category-card" href="?sayfa=ihaleler&durum=aktif">
            <strong>{aktif}</strong><span>AKTİF İHALELER</span>
          </a>
          <a class="ihalex-category-card" href="?sayfa=ihaleler&durum=pasif">
            <strong>{pasif}</strong><span>GEÇMİŞ İHALELER</span>
          </a>
          <a class="ihalex-category-card" href="?sayfa=ihaleler&durum=bekleyen">
            <strong>{bekleyen}</strong><span>TARİH İNCELEMEDE</span>
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if arama:
        alanlar = (
            df["baslik"].fillna("") + " " + df["il"].fillna("") + " "
            + df["ilce"].fillna("") + " " + df["kaynak"].fillna("")
        )
        sonuclar = df[alanlar.str.contains(arama, case=False, regex=False)]
        st.subheader(f"Arama sonuçları ({len(sonuclar)})")
        tablo_goster(sonuclar.head(30))
        st.divider()
    ana_sayfa_filtreleri_goster(df)
    st.markdown(
        "<div class='ihalex-section-head'><h3>Öne Çıkan İlanlar</h3>"
        "<a href='?sayfa=ihaleler&durum=aktif'>TÜM AKTİF İLANLAR →</a></div>",
        unsafe_allow_html=True,
    )
    aktifler = df[df["durum"] == "aktif"].sort_values("ihale_tarihi")
    vitrin_kartlari_goster(aktifler)
    ana_sayfa_haritasi_goster(df)
    st.markdown(
        "<div class='ihalex-section-head'><h3>En Yeni İhale Duyuruları</h3>"
        "<a href='?sayfa=ihaleler'>TÜMÜNÜ GÖRÜNTÜLE →</a></div>",
        unsafe_allow_html=True,
    )
    tablo_goster(df.head(8))
    st.markdown(
        """
        <div class="ihalex-service-grid">
          <div class="ihalex-service-card"><b>İlan Haritası</b>
            <small>İl ve ilçe bazında fırsat yoğunluğunu harita üzerinden keşfedin.</small></div>
          <div class="ihalex-service-card"><b>Telegram Alarmı</b>
            <small>Yeni aktif kantin ihaleleri yayımlandığında gecikmeden haberdar olun.</small></div>
          <div class="ihalex-service-card"><b>Resmî Kaynak Güvencesi</b>
            <small>İlanları yalnızca doğrulanmış MEB sayfaları ve resmî belgelerden izleyin.</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ihaleler_sayfasi(df: pd.DataFrame, gomulu: bool) -> None:
    st.title("Tüm kantin ihale ilanları")
    st.caption("ilan.gov.tr portal mantığından uyarlanan gelişmiş filtre ve sonuç görünümü.")
    with st.container(key="ihale_portali"):
        filtre_sutunu, sonuc_sutunu = st.columns([1, 3])
        with filtre_sutunu:
            st.markdown("#### Filtrele")
            kelime = st.text_input("Kelime", placeholder="Okul veya ilan adı")
            gun = st.selectbox(
                "Yayın dönemi", [30, 90, 180, 365], index=3,
                format_func=lambda x: f"Son {x} gün",
            )
            il_secenekleri = ["Tüm Türkiye"] + sorted(df["il"].dropna().unique())
            il_parametresi = str(st.query_params.get("il", "Tüm Türkiye"))
            il_indeksi = (
                il_secenekleri.index(il_parametresi)
                if il_parametresi in il_secenekleri else 0
            )
            il = st.selectbox("İlan yeri", il_secenekleri, index=il_indeksi)
            ilceler = sorted(
                df.loc[df["il"] == il, "ilce"].replace("", pd.NA).dropna().unique()
            )
            ilce = st.selectbox(
                "İlçe", ["Tüm ilçeler"] + ilceler, disabled=il == "Tüm Türkiye"
            )
            durum_parametresi = str(st.query_params.get("durum", "tumu"))
            durumlar = ["Tümü", "Aktif", "Pasif", "Doğrulanıyor"]
            varsayilan = {"aktif": 1, "pasif": 2, "bekleyen": 3}.get(durum_parametresi, 0)
            durum = st.selectbox("İlan durumu", durumlar, index=varsayilan)
    filtre = df[df["gun"] <= gun]
    if kelime:
        arama_alani = filtre["baslik"].fillna("") + " " + filtre["kaynak"].fillna("")
        filtre = filtre[arama_alani.str.contains(kelime, case=False, regex=False)]
    if il != "Tüm Türkiye":
        filtre = filtre[filtre["il"] == il]
    if ilce != "Tüm ilçeler":
        filtre = filtre[filtre["ilce"] == ilce]
    durum_kodu = {"Aktif": "aktif", "Pasif": "pasif", "Doğrulanıyor": "tarih_bekleniyor"}
    if durum in durum_kodu:
        filtre = filtre[filtre["durum"] == durum_kodu[durum]]
    with sonuc_sutunu:
        ust1, ust2 = st.columns([2, 1])
        siralama = ust1.selectbox(
            "Sıralama", ["En yeni yayın", "En yakın ihale tarihi", "Okul adına göre"]
        )
        gorunum = ust2.segmented_control(
            "Görünüm", ["Liste", "Kart"], default="Kart" if gomulu else "Liste"
        )
        if siralama == "En yakın ihale tarihi":
            filtre = filtre.sort_values("ihale_tarihi", na_position="last")
        elif siralama == "Okul adına göre":
            filtre = filtre.sort_values("baslik")
        else:
            filtre = filtre.sort_values("yayin_tarihi", ascending=False)
        sayfa_boyutu = 15 if gorunum == "Kart" else (30 if gomulu else 50)
        sayfa_sayisi = max((len(filtre) + sayfa_boyutu - 1) // sayfa_boyutu, 1)
        p1, p2 = st.columns([3, 1])
        p1.caption(f"{len(filtre)} resmî ihale bulundu · Son {gun} gün")
        sayfa = int(p2.number_input("Sayfa", 1, sayfa_sayisi, 1))
        baslangic = (sayfa - 1) * sayfa_boyutu
        parca = filtre.iloc[baslangic:baslangic + sayfa_boyutu]
        if gorunum == "Kart":
            kartlar_goster(parca)
        else:
            tablo_goster(parca)


def harita_sayfasi(df: pd.DataFrame, gomulu: bool) -> None:
    st.title("Türkiye fırsat haritası")
    st.caption("İl sınırları kalın, ilçe yoğunlukları ihale sayısına göre renklidir.")
    with st.container(key="harita_filtreleri"):
        h1, h2 = st.columns(2)
        il = h1.selectbox("İl", ["Tüm Türkiye"] + list(IL_ADLARI[1:]), key="web_harita_il")
        ilceler = ilce_secenekleri(il) if il != "Tüm Türkiye" else []
        ilce = h2.selectbox("İlçe", ["Tüm ilçeler"] + ilceler,
                            disabled=il == "Tüm Türkiye", key="web_harita_ilce")
    try:
        harita_df = harita_verisi_getir()
        secilen_il = None if il == "Tüm Türkiye" else il
        secilen_ilce = None if ilce == "Tüm ilçeler" else ilce
        figur = turkiye_haritasi(harita_df, secilen_il, secilen_ilce)
        if gomulu:
            figur.update_layout(height=520)
        st.plotly_chart(
            figur, width="stretch", key="web_turkiye_haritasi",
            config={"responsive": True, "scrollZoom": False, "displaylogo": False},
        )
        gorunen = harita_df
        if secilen_il:
            gorunen = gorunen[gorunen["il"] == secilen_il]
        if secilen_ilce:
            gorunen = gorunen[gorunen["ilce"] == secilen_ilce]
        st.caption(f"Seçili görünümde {int(gorunen['ilan_sayisi'].sum())} ihale gösteriliyor.")
        harita_disi = max(len(df) - int(harita_df["ilan_sayisi"].sum()), 0)
        if not secilen_il and harita_disi:
            st.caption(f"{harita_disi} kaydın ilçesi doğrulanırken ana listede görünmeye devam eder.")
    except Exception:
        logging.exception("Harita hazırlanamadı")
        st.error("Harita şu anda hazırlanamadı. Kısa süre sonra yeniden deneyin.")


def istatistik_sayfasi(df: pd.DataFrame) -> None:
    st.title("İhale istatistikleri")
    donem = st.segmented_control("Dönem", ["Son 6 ay", "Son 1 yıl"], default="Son 1 yıl")
    gun = 180 if donem == "Son 6 ay" else 365
    veri = df[df["gun"] <= gun]
    if veri.empty:
        st.info("Bu dönem için veri bulunmuyor.")
        return
    il_sayilari = veri.groupby("il", as_index=False).size().rename(columns={"size": "İhale"})
    il_sayilari = il_sayilari.sort_values("İhale", ascending=False).head(15)
    figur = px.bar(
        il_sayilari.sort_values("İhale"), x="İhale", y="il", orientation="h",
        labels={"il": "İl"}, color="İhale",
        color_continuous_scale=["#fff176", "#ffd21f", "#d71920"],
        title=f"{donem}: en çok ihale yayımlayan 15 il",
    )
    figur.update_layout(coloraxis_showscale=False, margin={"l": 0, "r": 0, "t": 55, "b": 0})
    st.plotly_chart(figur, width="stretch", config={"displaylogo": False})
    tekrarlar = tekrar_ihale_ozeti(veri)
    st.subheader("Tekrarlayan okul ihaleleri")
    st.caption("Aynı okul için yayın ve ihale tarihleri farklı olan tekrarlar gösterilir.")
    if tekrarlar.empty:
        st.success("Seçili dönemde tekrarlayan okul ihalesi bulunmadı.")
    else:
        st.dataframe(tekrarlar, width="stretch", hide_index=True)


def admin_giris_yapildi() -> bool:
    beklenen = os.getenv("IHALEX_ADMIN_PASSWORD", "")
    if not beklenen:
        st.error(
            "Yönetim alanı güvenlik gereği kapalı. İnternete açmadan önce "
            "IHALEX_ADMIN_PASSWORD sunucu sırrı tanımlanmalıdır."
        )
        return False
    if st.session_state.get("admin_yetkili"):
        return True
    with st.form("admin_giris"):
        parola = st.text_input("Yönetici parolası", type="password")
        giris = st.form_submit_button("Giriş yap", type="primary")
    if giris:
        if hmac.compare_digest(parola, beklenen):
            st.session_state["admin_yetkili"] = True
            st.rerun()
        else:
            st.error("Parola doğru değil.")
    return False


def yonetim_sayfasi() -> None:
    st.title("Yönetim")
    if not admin_giris_yapildi():
        return
    kaynak_kapsami_goster()
    st.divider()
    alarmlar = alarm_ozeti()
    aboneler = telegram_abone_ozeti()
    y1, y2, y3 = st.columns(3)
    y1.metric("Aktif abone", aboneler["aktif"])
    y2.metric("Bekleyen alarm", alarmlar.get("bekliyor", 0))
    y3.metric("Gönderilen", alarmlar.get("gonderildi", 0))
    st.subheader("Telegram")
    if not telegram_hazir():
        with st.form("telegram_kurulum", clear_on_submit=True):
            token = st.text_input("BotFather tokeni", type="password")
            bagla = st.form_submit_button("Botu bağla", type="primary")
        if bagla:
            try:
                telegram_baglantisini_kur(token)
                st.success("Telegram botu bağlandı.")
                st.rerun()
            except TelegramKurulumHatasi as hata:
                st.error(str(hata))
        return
    bot_linki = telegram_bot_baglantisi()
    if bot_linki:
        st.link_button("Telegram botunu aç", bot_linki)
    b1, b2, b3 = st.columns(3)
    if b1.button("Aboneleri yenile", width="stretch"):
        telegram_aboneleri_yenile()
        st.success("Aboneler yenilendi.")
    if b2.button("Test mesajı gönder", width="stretch"):
        sonuc = telegram_test_mesaji_gonder()
        st.success(f"{sonuc['gonderilen']} aboneye gönderildi.")
    if b3.button("Aktif ihaleleri gönder", type="primary", width="stretch"):
        aktif_ilanlari_kuyruga_al(yeniden_gonder=True)
        st.success(f"{bekleyenleri_gonder(limit=1000)} mesaj gönderildi.")
    abone_listesi = telegram_abone_listesi()
    if abone_listesi:
        st.dataframe(pd.DataFrame(abone_listesi), width="stretch", hide_index=True)


def uygulama() -> None:
    gomulu = str(st.query_params.get("embedded", "0")) == "1"
    stilleri_yukle(gomulu)
    banner_foto = gorsel_data_uri(str(BANNER_GORSELI))
    st.markdown(
        f"""
        <section class="ihalex-radar-banner"
                 style="--ihalex-banner-photo: url('{banner_foto}')"
                 aria-label="İhalex, Türkiye'nin İhale Fırsat Haritası">
          <div class="ihalex-radar-photo" role="img"
               aria-label="Sarı duotone okul kantini panoraması"></div>
          <div class="ihalex-radar-brand" role="img" aria-label="İHALEX">
            <span class="ihalex-human-i" aria-hidden="true"></span>
            <h1>HALE<span class="x">X</span></h1>
          </div>
          <div class="ihalex-radar-copy">
            <small>OKUL KANTİNİ İHALE AĞI</small>
            <strong>Türkiye’nin İhale Fırsat Haritası</strong>
          </div>
          <div class="ihalex-radar-signal" aria-label="81 il canlı tarama">
            <i class="ihalex-radar-sweep" aria-hidden="true"></i>
            <span>81 İL<br>CANLI</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    istenen = str(st.query_params.get("sayfa", "ana-sayfa"))
    varsayilan = SAYFA_ADLARI.get(istenen, "Ana Sayfa")
    if st.session_state.get("_ihalex_sayfa_parametresi") != istenen:
        st.session_state["ana_navigasyon"] = varsayilan
        st.session_state["_ihalex_sayfa_parametresi"] = istenen
    secim = st.segmented_control(
        "Ana menü", list(SAYFALAR), default=varsayilan,
        label_visibility="collapsed", key="ana_navigasyon",
    )
    sayfa = SAYFALAR.get(secim or "Ana Sayfa", "ana-sayfa")
    if sayfa != istenen:
        st.query_params["sayfa"] = sayfa
        st.session_state["_ihalex_sayfa_parametresi"] = sayfa
    df = veri_getir()
    if df.empty:
        st.warning("Son bir yıl içinde doğrulanmış ihale verisi bulunamadı.")
    elif sayfa == "ana-sayfa":
        ana_sayfa(df)
    elif sayfa == "ihaleler":
        ihaleler_sayfasi(df, gomulu)
    elif sayfa == "harita":
        harita_sayfasi(df, gomulu)
    elif sayfa == "istatistikler":
        istatistik_sayfasi(df)
    else:
        yonetim_sayfasi()
    st.markdown(
        "<div class='ihalex-footer'>İhalex · Resmî MEB kaynakları · "
        "Veriler 60 saniyede yenilenir · İhalex, MEB veya ilan.gov.tr'nin resmî sitesi değildir.</div>",
        unsafe_allow_html=True,
    )
    st_autorefresh(interval=60_000, limit=None, key="site_yenileme")


uygulama()
