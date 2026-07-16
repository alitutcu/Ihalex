"""İhalex'in hızlı, mobil uyumlu ve WebView içinde çalışabilen web arayüzü."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta
import html
import json
import logging
from pathlib import Path
import sqlite3
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from admin_kimlik import (
    AdminKimlikHatasi,
    admin_kimligini_dogrula,
    admin_kurulumu_gerekli,
    admin_oturumu_gecerli,
    admin_oturum_tokeni_olustur,
    admin_oturum_tokenini_dogrula,
    yerel_admin_olustur,
)
from analiz_motoru import (
    AnalizVerisiHatasi,
    OKUL_TURU_DONUSUM_ARALIKLARI,
    OKUL_TURU_DONUSUM_ORANLARI,
    OKUL_TURU_HARCAMA_KATSAYILARI,
    aday_analiz_raporu_olustur,
    analiz_matematigi_olustur,
    analizi_kaydet,
    manuel_duzeltme_kaydet,
    manuel_duzeltmeyi_kaldir,
    okul_tipi_belirle,
)
from harita_gosterici import turkiye_il_haritasi
from harita_motoru import IL_ADLARI
from ihale_belge_arsivi import arsiv_ozeti
from istatistik_motoru import okul_adi_ayikla, tekrar_ihale_ozeti
from meb_kaynaklari import kaynak_ozeti
from surum_bilgisi import GUNCEL_SURUM
from tarama_kontrolu import (
    manuel_tarama_iste,
    manuel_tarama_istegi_var,
    tarama_durumu_oku,
)
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
from veritabani import DB, ham_arsiv_ozeti, ihale_tarih_siniri, tablo_olustur
from yapay_zeka_analizi import ilan_kart_analizi


st.set_page_config(
    page_title="İhalex — Türkiye'nin İhale Fırsat Haritası",
    page_icon="📣",
    layout="wide",
    initial_sidebar_state="collapsed",
)


SAYFALAR = {
    "Ana Sayfa": "ana-sayfa",
    "İhaleler": "ihaleler",
    "İstatistikler": "istatistikler",
    "AI Analiz": "yapay-zeka-analizi",
    "Yönetim": "yonetim",
}
SAYFA_ADLARI = {deger: anahtar for anahtar, deger in SAYFALAR.items()}
BANNER_GORSELI = Path(__file__).resolve().parent / "assets" / "banner-school-cafeteria-source.jpg"
ADMIN_OTURUM_SURESI = timedelta(hours=3)
ADMIN_CEREZ_ADI = "ihalex_admin_oturum"
VERITABANI_SEMA_SURUMU = "2026-07-16-donusum-orani-v6"


@st.cache_data(show_spinner=False)
def gorsel_data_uri(dosya: str) -> str:
    yol = Path(dosya)
    if not yol.is_file():
        return ""
    kod = base64.b64encode(yol.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{kod}"


@st.cache_resource(show_spinner=False)
def veritabani_hazirla(sema_surumu: str) -> None:
    del sema_surumu  # Sürüm değeri Streamlit migration önbelleğini yeniler.
    tablo_olustur()


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
            --ihalex-paper: #e9e9e2;
        }}
        .stApp {{ background: var(--ihalex-paper); color: var(--ihalex-black); }}
        .block-container {{
            max-width: 1240px;
            padding: 1rem 1.4rem 4rem;
        }}
        [data-testid="stHeader"] {{ background: rgba(233,233,226,.94); }}
        #MainMenu, footer, .stAppDeployButton {{ display: none !important; }}
        [data-testid="stDataFrame"],
        [data-testid="stPlotlyChart"] {{
            background: #ffffff;
            border: 1px solid #bdbdb2;
            border-radius: 13px;
            box-shadow: 0 5px 16px rgba(17,17,17,.10);
            overflow: hidden;
        }}
        [data-testid="stDataFrame"] {{
            outline: 1px solid rgba(255,255,255,.7);
            outline-offset: -2px;
        }}
        .st-key-ana_sayfa_harita [data-testid="stPlotlyChart"] {{
            background: var(--ihalex-black);
            border: 0;
            border-radius: 8px;
            box-shadow: none;
        }}
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
            margin: 2.6rem 0 1rem;
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
            position: relative;
            isolation: isolate;
            display: flex;
            align-items: center;
            gap: clamp(.75rem, 1.4vw, 1.2rem);
            min-width: 0;
            min-height: 100%;
            padding: 1rem clamp(1.25rem, 3vw, 2.7rem);
            overflow: hidden;
        }}
        .ihalex-radar-brand::before,
        .ihalex-radar-brand::after {{
            content: "";
            position: absolute;
            z-index: 0;
            left: clamp(.15rem, 1vw, .8rem);
            top: 50%;
            width: clamp(104px, 12vw, 142px);
            aspect-ratio: 1;
            border-radius: 50%;
            transform: translateY(-50%);
        }}
        .ihalex-radar-brand::before {{
            background:
                radial-gradient(circle at 28% 24%, var(--ihalex-red) 0 3px, transparent 4px),
                radial-gradient(circle at 72% 34%, var(--ihalex-black) 0 2px, transparent 3px),
                radial-gradient(circle at 68% 74%, var(--ihalex-red) 0 2px, transparent 3px),
                repeating-radial-gradient(
                    circle at 50% 50%,
                    transparent 0 17px,
                    rgba(17,17,17,.24) 18px 19px,
                    transparent 20px 32px
                ),
                linear-gradient(
                    90deg,
                    transparent 49%, rgba(17,17,17,.20) 49% 51%, transparent 51%
                ),
                linear-gradient(
                    0deg,
                    transparent 49%, rgba(17,17,17,.20) 49% 51%, transparent 51%
                );
            opacity: .72;
        }}
        .ihalex-radar-brand::after {{
            background: conic-gradient(
                from -34deg,
                transparent 0 72%,
                rgba(215,25,32,.36) 82%,
                transparent 93%
            );
            animation: ihalex-marka-radar 5.5s linear infinite;
            transform-origin: 50% 50%;
        }}
        .ihalex-radar-brand > * {{
            position: relative;
            z-index: 1;
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
        .ihalex-radar-brand .i-letter {{
            position: relative;
            display: inline-block;
            color: var(--ihalex-black);
        }}
        .ihalex-radar-brand .i-letter::after {{
            content: "";
            position: absolute;
            width: .28em;
            aspect-ratio: 1;
            left: 50%;
            top: -.25em;
            transform: translateX(-50%);
            border-radius: 50%;
            background: var(--ihalex-red);
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
            max-width: 360px;
            font-size: clamp(1rem, 1.7vw, 1.4rem);
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
        @keyframes ihalex-marka-radar {{
            to {{ transform: translateY(-50%) rotate(360deg); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .ihalex-radar-sweep,
            .ihalex-radar-brand::after {{ animation: none; }}
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
        .st-key-admin_tarama_kontrolu {{
            background: white;
            border: 1px solid #deded5;
            border-left: 6px solid var(--ihalex-yellow);
            border-radius: 12px;
            padding: .85rem 1rem .55rem;
            margin-bottom: 1rem;
        }}
        .st-key-admin_tarama_kontrolu [data-testid="stProgress"] > div > div {{
            min-height: .55rem;
        }}
        .st-key-admin_giris_karti {{
            max-width: 520px;
            margin: 2rem auto;
            padding: 1.25rem 1.35rem .9rem;
            background: #ffffff;
            border: 1px solid #bdbdb2;
            border-top: 7px solid var(--ihalex-yellow);
            border-radius: 14px;
            box-shadow: 0 8px 24px rgba(17,17,17,.12);
        }}
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
            grid-template-columns: 1.45fr 2.1fr .82fr .82fr .72fr .82fr;
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
            border: 1px solid #b7b7ad;
            border-top: 0;
            padding: .8rem .85rem;
            text-decoration: none !important;
            transition: background .15s ease;
        }}
        .ihalex-result-row + .ihalex-result-row {{
            border-top: 2px solid #a5a59a;
        }}
        .ihalex-result-row:nth-of-type(even) {{ background: #f5f5ef; }}
        .ihalex-result-row:hover {{ background: #fff9d7; }}
        .ihalex-result-row:last-child {{ border-radius: 0 0 7px 7px; }}
        .ihalex-result-row .kurum {{
            color: #5a5a54;
            font-size: .73rem;
            font-weight: 750;
            text-transform: uppercase;
        }}
        .ihalex-result-row .okul {{ font-size: .88rem; font-weight: 850; }}
        .ihalex-result-row .tarih,
        .ihalex-result-row .sehir,
        .ihalex-result-row .ilce {{
            color: #4e4e49;
            font-size: .78rem;
            font-weight: 700;
        }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: #ffffff;
            border-color: #b5b5aa !important;
            box-shadow: 0 4px 14px rgba(17,17,17,.09);
        }}
        .ihalex-card-title {{
            color: #111111 !important;
            font-size: 1rem;
            font-weight: 900;
            line-height: 1.35;
        }}
        .ihalex-card-meta {{ color: #3f3f3a !important; font-size: .82rem; margin-top: .35rem; }}
        .ihalex-active-badge {{
            display: inline-flex;
            align-items: center;
            width: fit-content;
            margin-bottom: .55rem;
            padding: .24rem .55rem;
            border-radius: 999px;
            background: #166534;
            color: #ffffff !important;
            font-size: .68rem;
            font-weight: 900;
            letter-spacing: .055em;
        }}
        [class*="st-key-ai_ilan_karti_"] {{
            background: #ffffff;
            border: 1px solid #a9a99f;
            border-top: 7px solid var(--ihalex-yellow);
            border-radius: 14px;
            padding: .95rem 1rem .75rem;
            box-shadow: 0 7px 18px rgba(17,17,17,.10);
            height: 100%;
        }}
        [class*="st-key-ai_ilan_karti_"] [data-testid="stMetric"] {{
            background: #f5f5ef;
            border-radius: 10px;
            padding: .55rem .65rem;
            box-shadow: none;
        }}
        [class*="st-key-ai_ilan_karti_"] [data-testid="stMetricLabel"] {{
            font-size: .72rem;
        }}
        [class*="st-key-ai_ilan_karti_"] [data-testid="stMetricValue"] {{
            font-size: 1.12rem;
        }}
        .ihalex-ai-kicker {{
            color: var(--ihalex-red);
            font-size: .7rem;
            font-weight: 950;
            letter-spacing: .075em;
            text-transform: uppercase;
            margin-bottom: .35rem;
        }}
        .ihalex-ai-school {{
            color: var(--ihalex-black);
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.28;
            min-height: 2.7rem;
        }}
        .ihalex-ai-meta {{
            color: #585851;
            font-size: .78rem;
            margin: .35rem 0 .65rem;
        }}
        .ihalex-ai-result {{
            background: #111111;
            color: #ffffff;
            border-left: 6px solid var(--ihalex-red);
            border-radius: 9px;
            padding: .75rem .85rem;
            margin: .6rem 0;
        }}
        .ihalex-ai-result strong {{ color: var(--ihalex-yellow); }}
        .st-key-ai_analiz_filtreleri {{
            background: #ffffff;
            border: 1px solid #bdbdb2;
            border-radius: 12px;
            padding: .75rem .9rem .25rem;
            margin-bottom: 1rem;
        }}
        .ihalex-index-shell {{
            border: 1px solid rgba(17,17,17,.16);
            border-radius: 18px;
            background: #f8f7ef;
            box-shadow: 0 18px 42px rgba(17,17,17,.08);
            overflow: hidden;
            margin-top: .55rem;
        }}
        .ihalex-index-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 14px 18px;
            color: #FFD21F;
            background: #111111;
            border-bottom: 4px solid #D71920;
        }}
        .ihalex-index-head strong {{
            font-size: 1rem;
            letter-spacing: .035em;
            text-transform: uppercase;
        }}
        .ihalex-index-head span {{
            padding: 5px 10px;
            border: 1px solid rgba(255,210,31,.48);
            border-radius: 999px;
            font-size: .72rem;
            font-weight: 900;
        }}
        .ihalex-index-list {{ display: grid; gap: 0; }}
        .ihalex-index-item {{
            display: grid;
            grid-template-columns: 92px minmax(0, 1fr) 170px 34px;
            gap: 16px;
            align-items: center;
            min-height: 118px;
            padding: 14px 16px;
            color: #111111 !important;
            text-decoration: none !important;
            background: #ffffff;
            border-bottom: 1px solid rgba(17,17,17,.16);
            transition: transform .16s ease, background .16s ease;
        }}
        .ihalex-index-item:last-child {{ border-bottom: 0; }}
        .ihalex-index-item:hover {{ background: #fff9d8; transform: translateX(3px); }}
        .ihalex-index-date {{
            display: grid;
            place-items: center;
            min-height: 76px;
            padding: 8px;
            color: #FFD21F;
            background: #111111;
            border-radius: 12px;
            box-shadow: inset 0 -4px 0 #D71920;
            text-align: center;
        }}
        .ihalex-index-date b {{ font-size: 1.4rem; line-height: 1; }}
        .ihalex-index-date small {{
            font-size: .62rem;
            font-weight: 900;
            letter-spacing: .06em;
            text-transform: uppercase;
        }}
        .ihalex-index-main {{ min-width: 0; }}
        .ihalex-index-badge {{
            display: inline-flex;
            margin-bottom: 5px;
            color: #D71920;
            font-size: .66rem;
            font-weight: 950;
            letter-spacing: .06em;
            text-transform: uppercase;
        }}
        .ihalex-index-title {{
            display: -webkit-box;
            overflow: hidden;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 2;
            font-size: 1rem;
            font-weight: 900;
            line-height: 1.25;
        }}
        .ihalex-index-meta {{
            margin-top: 7px;
            color: #5b5a54;
            font-size: .76rem;
            font-weight: 700;
        }}
        .ihalex-index-tender {{
            padding: 10px 12px;
            border: 1px solid rgba(17,17,17,.14);
            border-radius: 10px;
            background: #f4f2e8;
        }}
        .ihalex-index-tender small {{
            display: block;
            color: #77746a;
            font-size: .62rem;
            font-weight: 900;
            text-transform: uppercase;
        }}
        .ihalex-index-tender strong {{ font-size: .88rem; }}
        .ihalex-index-arrow {{
            display: grid;
            place-items: center;
            width: 32px;
            height: 32px;
            color: #ffffff;
            background: #D71920;
            border-radius: 50%;
            font-size: 1rem;
            font-weight: 950;
        }}
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
                margin-top: 1.5rem;
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
            .st-key-ihale_portali [data-testid="stColumn"],
            .st-key-ana_sayfa_portal [data-testid="stColumn"] {{
                min-width: 100% !important;
                flex-basis: 100% !important;
            }}
            .st-key-ana_sayfa_portal [data-testid="stHorizontalBlock"]:has(
                > [data-testid="stColumn"] .ihalex-filter-column-marker
            ) {{
                flex-wrap: nowrap !important;
                align-items: stretch !important;
                gap: .45rem !important;
            }}
            .st-key-ana_sayfa_portal [data-testid="stColumn"]:has(
                .ihalex-filter-column-marker
            ) {{
                min-width: 34% !important;
                flex: 0 0 34% !important;
            }}
            .st-key-ana_sayfa_portal [data-testid="stColumn"]:has(
                .ihalex-result-column-marker
            ) {{
                min-width: 0 !important;
                flex: 1 1 66% !important;
            }}
            .ihalex-filter-column-marker,
            .ihalex-result-column-marker {{ display: none; }}
            .st-key-ana_sayfa_portal input,
            .st-key-ana_sayfa_portal [data-baseweb="select"] > div {{
                min-width: 0 !important;
                font-size: 13px !important;
            }}
            .ihalex-result-header {{ display: none; }}
            .ihalex-result-row {{
                grid-template-columns: 1fr;
                gap: .35rem;
                border-top: 1px solid #b7b7ad;
                border-radius: 7px;
                margin-bottom: .55rem;
            }}
            .ihalex-result-row + .ihalex-result-row {{
                border-top: 2px solid #919187;
            }}
            .ihalex-result-row span {{
                display: grid;
                grid-template-columns: 7.4rem minmax(0, 1fr);
                gap: .55rem;
                align-items: start;
            }}
            .ihalex-result-row span::before {{
                content: attr(data-label);
                color: #6a6a63;
                font-size: .66rem;
                font-weight: 900;
                letter-spacing: .025em;
                text-transform: uppercase;
            }}
            .ihalex-index-head {{
                align-items: flex-start;
                flex-direction: column;
                gap: .55rem;
                padding: 12px 14px;
            }}
            .ihalex-index-item {{
                grid-template-columns: 66px minmax(0, 1fr) 28px;
                gap: 10px;
                min-height: 104px;
                padding: 12px 10px;
            }}
            .ihalex-index-date {{
                min-height: 68px;
                padding: 6px;
                border-radius: 10px;
            }}
            .ihalex-index-date b {{ font-size: 1.18rem; }}
            .ihalex-index-title {{ font-size: .9rem; }}
            .ihalex-index-meta {{ font-size: .7rem; }}
            .ihalex-index-tender {{
                grid-column: 2;
                padding: 6px 8px;
            }}
            .ihalex-index-arrow {{
                grid-column: 3;
                grid-row: 1 / span 2;
                width: 28px;
                height: 28px;
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


def analiz_karti_url(ilan_id: object) -> str:
    try:
        kimlik = int(ilan_id)
    except (TypeError, ValueError):
        kimlik = 0
    return f"?sayfa=yapay-zeka-analizi&ilan={kimlik}"


def ilan_adi_olustur(satir: pd.Series) -> str:
    okul = str(satir.get("okul_adi") or "").strip()
    if okul and okul != "Okul adı doğrulanıyor":
        return f"{okul} Kantin İhalesi"
    baslik = str(satir.get("baslik") or "").strip()
    sade = baslik.casefold().replace("ı", "i")
    if not baslik or "tiklay" in sade:
        return "Kantin ihalesi · okul adı doğrulanıyor"
    return baslik


@st.cache_data(ttl=60, show_spinner=False)
def veri_getir() -> pd.DataFrame:
    sorgu = """
        WITH sirali AS (
            SELECT d.id AS ilan_id, d.baslik,
                   COALESCE(NULLIF(TRIM(m.il), ''), k.il) AS il,
                   COALESCE(NULLIF(TRIM(m.ilce), ''), k.ilce) AS ilce,
                   k.kurum_adi AS kaynak,
                   d.yayin_tarihi, d.ihale_tarihi, d.durum,
                   CASE WHEN d.eslesme_turu='ek_dosya' THEN d.url
                        ELSE COALESCE(NULLIF(d.detay_url, ''), d.url) END AS ihale_url,
                   d.ilk_gorulme, d.eslesme_turu,
                   COALESCE(NULLIF(TRIM(m.okul_adi), ''), a.okul_adi)
                       AS belge_okul_adi,
                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu) AS okul_turu,
                   a.adres,
                   COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) AS ogrenci_sayisi,
                   COALESCE(m.personel_sayisi, a.personel_sayisi) AS personel_sayisi,
                   COALESCE(
                       m.ogrenci_donusum_orani,
                       CASE
                           WHEN LOWER(REPLACE(
                               COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                               'İ', 'i'
                           )) LIKE '%ilkokul%' THEN 0.36
                           WHEN LOWER(REPLACE(
                               COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                               'İ', 'i'
                           )) LIKE '%ortaokul%' THEN 0.54
                           WHEN LOWER(REPLACE(
                               COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                               'İ', 'i'
                           )) LIKE '%meslek%lise%' THEN 0.72
                           WHEN LOWER(REPLACE(
                               COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                               'İ', 'i'
                           )) LIKE '%lise%' THEN 0.6525
                           ELSE 0.54
                       END
                   ) AS ogrenci_donusum_orani,
                   a.muhammen_bedel,
                   COALESCE(m.muhammen_bedel_aylik, a.muhammen_bedel_aylik)
                       AS muhammen_bedel_aylik,
                   COALESCE(m.muhammen_bedel_yillik, a.muhammen_bedel_yillik)
                       AS muhammen_bedel_yillik,
                   a.muhammen_bedel_donemi,
                   a.sartname_bedeli, a.gecici_teminat, a.kantin_alani_m2,
                   a.kira_suresi_ay, a.belge_guveni,
                   COALESCE(bv.ekonomik_katsayi, 1.00) AS ekonomik_katsayi,
                   COALESCE(bv.gelir_katsayi, 1.00) AS gelir_katsayi,
                   COALESCE(bv.ticari_hareketlilik_katsayi, 1.00)
                   AS ticari_hareketlilik_katsayi,
                   COALESCE(bv.veri_kaynagi, 'Henüz bağlanmadı') AS bolge_veri_kaynagi,
                   ka.sonuc_json AS yatirim_raporu_json,
                   (SELECT COUNT(*) FROM ihale_belgeleri b
                    WHERE b.aday_id=d.id AND b.durum IN (
                        'analiz_edildi','analiz_bekliyor','arsivlendi'
                    ))
                   AS belge_sayisi,
                   (SELECT COUNT(*) FROM duyuru_adaylari child
                    WHERE child.detay_url=d.url
                      AND child.eslesme_turu='ek_dosya') AS ek_belge_sayisi,
                   ROW_NUMBER() OVER (
                       PARTITION BY CASE
                           WHEN d.eslesme_turu='ek_dosya'
                            AND (SELECT COUNT(*) FROM duyuru_adaylari kardes
                                 WHERE kardes.detay_url=d.detay_url
                                   AND kardes.eslesme_turu='ek_dosya') > 1
                            AND NULLIF(TRIM(COALESCE(m.okul_adi, a.okul_adi)), '')
                                IS NOT NULL
                           THEN COALESCE(d.detay_url, '') || '|' || LOWER(
                               COALESCE(m.okul_adi, a.okul_adi)
                           )
                           WHEN d.eslesme_turu='ek_dosya'
                            AND (SELECT COUNT(*) FROM duyuru_adaylari kardes
                                 WHERE kardes.detay_url=d.detay_url
                                   AND kardes.eslesme_turu='ek_dosya') > 1
                           THEN d.url
                           ELSE COALESCE(NULLIF(d.detay_url, ''), d.url)
                       END
                        ORDER BY CASE
                            WHEN NULLIF(TRIM(COALESCE(m.okul_adi, a.okul_adi)), '')
                                     IS NOT NULL
                             AND NULLIF(TRIM(COALESCE(m.okul_turu, a.okul_turu)), '')
                                     IS NOT NULL
                             AND COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) IS NOT NULL
                             AND COALESCE(
                                     m.muhammen_bedel_aylik,
                                     a.muhammen_bedel_aylik
                                 ) IS NOT NULL
                            THEN 0 ELSE 1
                        END,
                        CASE d.eslesme_turu
                            WHEN 'detay' THEN 0 WHEN 'toplu_dosya' THEN 1
                            WHEN 'dosya' THEN 2 ELSE 3 END, d.id
                   ) AS sira
            FROM duyuru_adaylari d
            JOIN kaynaklar k ON k.id=d.kaynak_id
            LEFT JOIN ilan_analiz_verileri a ON a.aday_id=d.id
            LEFT JOIN analiz_manuel_duzeltmeleri m ON m.aday_id=d.id
            LEFT JOIN bolge_verileri bv
              ON bv.il=COALESCE(NULLIF(TRIM(m.il), ''), k.il)
             AND bv.ilce=COALESCE(NULLIF(TRIM(m.ilce), ''), k.ilce, '')
            LEFT JOIN kantin_yatirim_analizleri ka ON ka.aday_id=d.id
            WHERE d.yayin_tarihi >= ?
        )
        SELECT ilan_id, baslik, il, ilce, kaynak, yayin_tarihi, ihale_tarihi,
               durum, ihale_url, ilk_gorulme, eslesme_turu,
               belge_okul_adi, okul_turu, adres,
               ogrenci_sayisi, personel_sayisi, ogrenci_donusum_orani,
               muhammen_bedel,
               muhammen_bedel_aylik, muhammen_bedel_yillik,
               muhammen_bedel_donemi,
               sartname_bedeli, gecici_teminat, kantin_alani_m2,
               kira_suresi_ay, belge_guveni, belge_sayisi, ek_belge_sayisi,
               ekonomik_katsayi, gelir_katsayi, ticari_hareketlilik_katsayi,
               bolge_veri_kaynagi, yatirim_raporu_json
        FROM sirali
        WHERE sira=1
          AND NOT (eslesme_turu<>'ek_dosya' AND ek_belge_sayisi>1)
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
    basliktan_okul = df["baslik"].map(okul_adi_ayikla)
    df["okul_adi"] = df["belge_okul_adi"].replace("", pd.NA).fillna(
        basliktan_okul
    ).fillna("Okul adı doğrulanıyor")
    df["okul_turu"] = df["okul_turu"].replace("", pd.NA).fillna(
        "Okul türü doğrulanıyor"
    )
    df["ilan_adi"] = df.apply(ilan_adi_olustur, axis=1)
    df["analize_hazir"] = (
        (df["okul_adi"] != "Okul adı doğrulanıyor")
        & (df["okul_turu"] != "Okul türü doğrulanıyor")
        & df["ilce"].str.strip().ne("")
        & df["ihale_tarihi"].notna()
        & df["ogrenci_sayisi"].notna()
        & df["muhammen_bedel_aylik"].notna()
    )
    df["kamusal_hazir"] = (
        (df["okul_adi"] != "Okul adı doğrulanıyor")
        & df["ihale_tarihi"].notna()
        & df["durum"].isin(["aktif", "pasif"])
    )
    df["ilce"] = df["ilce"].fillna("")
    df["gun"] = (pd.Timestamp(date.today()) - df["yayin_tarihi"]).dt.days.clip(lower=0)
    df["durum_etiketi"] = df["durum"].map({
        "aktif": "🟢 Aktif",
        "pasif": "⚫ Pasif",
        "tarih_bekleniyor": "🟡 Doğrulanıyor",
    }).fillna("🟡 Doğrulanıyor")
    return df


def tablo_goster(veri: pd.DataFrame) -> None:
    if veri.empty:
        st.info("Bu filtrelerle eşleşen ihale bulunamadı.")
        return
    gorunum = veri.rename(columns={
        "ilan_adi": "İhale", "il": "İl", "ilce": "İlçe", "kaynak": "MEB kaynağı",
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


def kartlar_goster(veri: pd.DataFrame, *, analiz_baglantisi: bool = False) -> None:
    if veri.empty:
        st.info("Bu filtrelerle eşleşen ihale bulunamadı.")
        return
    for _, satir in veri.iterrows():
        with st.container(border=True):
            baslik = html.escape(str(satir["ilan_adi"] or "Kantin ihalesi"))
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
            resmi_url = str(satir["ihale_url"])
            if analiz_baglantisi:
                st.link_button(
                    "AI analiz kartını aç",
                    analiz_karti_url(satir["ilan_id"]),
                    width="stretch",
                )
            elif resmi_meb_url(resmi_url):
                st.link_button("Resmî ilanı aç", resmi_url, width="stretch")


def vitrin_kartlari_goster(veri: pd.DataFrame) -> None:
    """Ana sayfadaki öne çıkan ilanları portal kartlarıyla gösterir."""
    if veri.empty:
        st.info("Şu anda öne çıkarılacak aktif ihale bulunmuyor.")
        return
    kolonlar = st.columns(3)
    for sira, (_, satir) in enumerate(veri.head(6).iterrows()):
        with kolonlar[sira % 3]:
            with st.container(border=True, key=f"vitrin_karti_{sira}"):
                st.html(
                    "<div class='ihalex-active-badge'>AKTİF İHALE</div>"
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
                st.link_button(
                    "AI analiz kartını aç",
                    analiz_karti_url(satir["ilan_id"]),
                    width="stretch",
                )


def portal_satirlari_goster(veri: pd.DataFrame) -> None:
    """Ana sayfadaki 12'li kaynak-okul-tarih-konum sonuç satırları."""
    if veri.empty:
        st.info("Seçilen filtrelerle eşleşen ilan bulunamadı.")
        return
    parcalar = [
        "<div class='ihalex-result-header'><span>MEB KAYNAĞI</span>"
        "<span>OKUL ADI</span><span>İLAN TARİHİ</span><span>İHALE TARİHİ</span>"
        "<span>ŞEHİR</span><span>İLÇE</span></div>"
    ]
    for _, satir in veri.iterrows():
        url = analiz_karti_url(satir["ilan_id"])
        tarih = satir["ihale_tarihi"]
        ihale_tarihi = tarih.strftime("%d.%m.%Y") if pd.notna(tarih) else "İnceleniyor"
        yayin_tarihi = satir["yayin_tarihi"].strftime("%d.%m.%Y")
        ilce = str(satir["ilce"] or "Doğrulanıyor")
        parcalar.append(
            "<a class='ihalex-result-row' href='"
            + html.escape(url, quote=True) + "'>"
            + "<span class='kurum' data-label='MEB Kaynağı'>"
            + html.escape(str(satir["kaynak"])) + "</span>"
            + "<span class='okul' data-label='Okul Adı'>"
            + html.escape(str(satir["okul_adi"])) + "</span>"
            + "<span class='tarih' data-label='İlan Tarihi'>"
            + html.escape(yayin_tarihi) + "</span>"
            + "<span class='tarih' data-label='İhale Tarihi'>"
            + html.escape(ihale_tarihi) + "</span>"
            + "<span class='sehir' data-label='Şehir'>"
            + html.escape(str(satir["il"])) + "</span>"
            + "<span class='ilce' data-label='İlçe'>"
            + html.escape(ilce) + "</span></a>"
        )
    st.markdown("".join(parcalar), unsafe_allow_html=True)


def ana_sayfa_filtreleri_goster(df: pd.DataFrame) -> None:
    """Ana sayfada görünür gelişmiş filtre ve ilan sonuçlarını gösterir."""
    df = df[df["durum"] == "aktif"].copy()
    st.markdown(
        "<div class='ihalex-section-head'><h3>İhale Filtreleri ve Sonuçları</h3>"
        "<a href='?sayfa=ihaleler'>GELİŞMİŞ İLAN SAYFASI →</a></div>",
        unsafe_allow_html=True,
    )
    with st.container(key="ana_sayfa_portal"):
        filtre_sutunu, sonuc_sutunu = st.columns(
            [1, 4],
            gap="medium",
            vertical_alignment="top",
            border=True,
        )
        with filtre_sutunu:
            st.html("<span class='ihalex-filter-column-marker'></span>")
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
            st.selectbox(
                "İlan durumu", ["Aktif"], disabled=True,
                key="ana_filtre_durum_aktif",
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
            arama_alani = (
                filtre["okul_adi"].fillna("") + " "
                + filtre["baslik"].fillna("") + " "
                + filtre["kaynak"].fillna("")
            )
            filtre = filtre[arama_alani.str.contains(kelime, case=False, regex=False)]
        if il != "Tüm Türkiye":
            filtre = filtre[filtre["il"] == il]
        if ilce != "Tüm ilçeler":
            filtre = filtre[filtre["ilce"] == ilce]
        if kaynak != "Tüm MEB kaynakları":
            filtre = filtre[filtre["kaynak"] == kaynak]
        with sonuc_sutunu:
            st.html("<span class='ihalex-result-column-marker'></span>")
            siralama = st.selectbox(
                "Sıralama", ["En yeni yayın", "En yakın ihale tarihi", "Okul adına göre"],
                key="ana_filtre_siralama",
            )
            if siralama == "En yakın ihale tarihi":
                filtre = filtre.sort_values("ihale_tarihi", na_position="last")
            elif siralama == "Okul adına göre":
                filtre = filtre.sort_values("okul_adi")
            else:
                filtre = filtre.sort_values("yayin_tarihi", ascending=False)
            parca = filtre.head(12)
            if parca.empty:
                st.info("Bu filtrelerle eşleşen aktif ihale bulunamadı.")
            else:
                ihale_indeksi_goster(
                    parca,
                    toplam=len(filtre),
                    sayfa=1,
                    sayfa_sayisi=max((len(filtre) + 11) // 12, 1),
                )


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
        "<div class='ihalex-section-head'><h3>İl Fırsat Haritası</h3>"
        "<a href='?sayfa=ihaleler'>HARİTADAKİ İLANLARI AÇ →</a></div>",
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
        st.caption(
            "Yeşil illerde aktif ihale bulunur. İlanları görmek için haritada bir ile tıklayın."
        )
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
    # Aktiflik yalnız ihale tarihine bağlıdır; analiz alanlarının tamamlanması
    # ayrı bir veri kalite durumudur ve aktif ilan sayısını azaltmaz.
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
        sonuclar = df[
            alanlar.str.contains(arama, case=False, regex=False)
            & df["analize_hazir"]
        ]
        st.subheader(f"Arama Sonuçları Tablosu ({len(sonuclar)})")
        portal_satirlari_goster(sonuclar.head(30))
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
        "<div class='ihalex-section-head'><h3>En Yeni İlanlar Tablosu</h3>"
        "<a href='?sayfa=ihaleler'>TÜMÜNÜ GÖRÜNTÜLE →</a></div>",
        unsafe_allow_html=True,
    )
    portal_satirlari_goster(df[df["analize_hazir"]].head(8))
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


def ihale_indeksi_goster(
    veri: pd.DataFrame,
    *,
    toplam: int,
    sayfa: int,
    sayfa_sayisi: int,
) -> None:
    """İlanları Excel görünümü yerine erişilebilir bir portal indeksinde göster."""
    aylar = (
        "OCA", "ŞUB", "MAR", "NİS", "MAY", "HAZ",
        "TEM", "AĞU", "EYL", "EKİ", "KAS", "ARA",
    )
    satirlar: list[str] = []
    for _, satir in veri.iterrows():
        yayin = pd.to_datetime(satir.get("yayin_tarihi"), errors="coerce")
        ihale = pd.to_datetime(satir.get("ihale_tarihi"), errors="coerce")
        gun = f"{int(yayin.day):02d}" if pd.notna(yayin) else "--"
        ay = aylar[int(yayin.month) - 1] if pd.notna(yayin) else "TARİH"
        yil = str(int(yayin.year)) if pd.notna(yayin) else "--"
        ihale_metni = ihale.strftime("%d.%m.%Y") if pd.notna(ihale) else "Doğrulanıyor"
        durum = str(satir.get("durum") or "")
        durum_etiketi = {
            "aktif": "AKTİF İHALE",
            "pasif": "GEÇMİŞ İHALE",
            "tarih_bekleniyor": "TARİH DOĞRULANIYOR",
        }.get(durum, "MEB İHALESİ")
        okul = str(satir.get("ilan_adi") or satir.get("baslik") or "Kantin ihalesi")
        konum = " · ".join(
            parca for parca in (
                str(satir.get("il") or "").strip(),
                str(satir.get("ilce") or "").strip(),
                str(satir.get("kaynak") or "").strip(),
            ) if parca
        )
        analize_hazir = bool(satir.get("analize_hazir"))
        url = (
            analiz_karti_url(satir.get("ilan_id"))
            if analize_hazir
            else str(satir.get("ihale_url") or "#")
        )
        hedef = "" if url.startswith("?") else ' target="_blank" rel="noopener"'
        satirlar.append(f"""
            <a class="ihalex-index-item" href="{html.escape(url, quote=True)}"{hedef}>
              <span class="ihalex-index-date">
                <small>{html.escape(ay)}</small><b>{html.escape(gun)}</b><small>{html.escape(yil)}</small>
              </span>
              <span class="ihalex-index-main">
                <span class="ihalex-index-badge">{html.escape(durum_etiketi)}</span>
                <span class="ihalex-index-title">{html.escape(okul)}</span>
                <span class="ihalex-index-meta">{html.escape(konum)}</span>
              </span>
              <span class="ihalex-index-tender">
                <small>İhale tarihi</small><strong>{html.escape(ihale_metni)}</strong>
              </span>
              <span class="ihalex-index-arrow">→</span>
            </a>
        """)
    indeks_html = "".join(satirlar).replace("\n", "")
    st.markdown(
        f'<section class="ihalex-index-shell">'
        f'<header class="ihalex-index-head">'
        f'<strong>Resmî MEB Kantin İhale İndeksi</strong>'
        f'<span>{toplam} sonuç · {sayfa}/{sayfa_sayisi}. sayfa</span>'
        f'</header><div class="ihalex-index-list">{indeks_html}</div></section>',
        unsafe_allow_html=True,
    )


def ihaleler_sayfasi(df: pd.DataFrame, gomulu: bool) -> None:
    del gomulu
    st.title("Kantin İhale İlanları")
    st.caption(
        "Resmî MEB duyurularını yer, durum ve tarihe göre filtreleyin; "
        "ilan satırından belgeye veya hazır AI analizine ulaşın."
    )
    with st.container(key="ihale_portali"):
        f1, f2, f3, f4 = st.columns([2.2, 1.15, 1.15, 1.1])
        kelime = f1.text_input(
            "İlanlarda ara", placeholder="Okul, ilçe veya MEB kaynağı"
        ).strip()
        il_secenekleri = ["Tüm Türkiye"] + sorted(df["il"].dropna().unique())
        il_parametresi = str(st.query_params.get("il", "Tüm Türkiye"))
        il_indeksi = il_secenekleri.index(il_parametresi) if il_parametresi in il_secenekleri else 0
        il = f2.selectbox("İl", il_secenekleri, index=il_indeksi)
        ilceler = sorted(
            df.loc[df["il"] == il, "ilce"].replace("", pd.NA).dropna().unique()
        )
        ilce = f3.selectbox(
            "İlçe", ["Tüm ilçeler"] + ilceler, disabled=il == "Tüm Türkiye"
        )
        durum_parametresi = str(st.query_params.get("durum", "tumu"))
        durumlar = ["Tümü", "Aktif", "Pasif", "Doğrulanıyor"]
        durum_indeksi = {"aktif": 1, "pasif": 2, "bekleyen": 3}.get(
            durum_parametresi, 0
        )
        durum = f4.selectbox("Durum", durumlar, index=durum_indeksi)
        a1, a2, a3 = st.columns([1, 1.35, 2.25])
        gun = a1.selectbox(
            "Yayın dönemi", [30, 90, 180, 365], index=3,
            format_func=lambda deger: f"Son {deger} gün",
        )
        siralama = a2.selectbox(
            "Sıralama", ["En yeni yayın", "En yakın ihale", "Okul adına göre"]
        )
        a3.markdown(
            '<div style="height:29px"></div><div style="padding:10px 14px;'
            'border-radius:10px;background:#111111;color:#FFD21F;font-weight:900;'
            'font-size:.8rem;">İHALEX · RESMÎ MEB KAYNAK İNDEKSİ</div>',
            unsafe_allow_html=True,
        )

    filtre = df[df["gun"] <= gun].copy()
    if kelime:
        arama_alani = (
            filtre["baslik"].fillna("") + " "
            + filtre["okul_adi"].fillna("") + " "
            + filtre["kaynak"].fillna("") + " "
            + filtre["ilce"].fillna("")
        )
        filtre = filtre[arama_alani.str.contains(kelime, case=False, regex=False)]
    if il != "Tüm Türkiye":
        filtre = filtre[filtre["il"] == il]
    if ilce != "Tüm ilçeler":
        filtre = filtre[filtre["ilce"] == ilce]
    durum_kodu = {
        "Aktif": "aktif", "Pasif": "pasif", "Doğrulanıyor": "tarih_bekleniyor"
    }
    if durum in durum_kodu:
        filtre = filtre[filtre["durum"] == durum_kodu[durum]]
    if siralama == "En yakın ihale":
        filtre = filtre.sort_values("ihale_tarihi", na_position="last")
    elif siralama == "Okul adına göre":
        filtre = filtre.sort_values("ilan_adi")
    else:
        filtre = filtre.sort_values("yayin_tarihi", ascending=False)

    filtre_imzasi = (kelime, il, ilce, durum, gun, siralama)
    if st.session_state.get("ihale_index_imzasi") != filtre_imzasi:
        st.session_state["ihale_index_imzasi"] = filtre_imzasi
        st.session_state["ihale_index_sayfa"] = 1
    sayfa_boyutu = 12
    sayfa_sayisi = max((len(filtre) + sayfa_boyutu - 1) // sayfa_boyutu, 1)
    sayfa = min(max(int(st.session_state.get("ihale_index_sayfa", 1)), 1), sayfa_sayisi)
    st.session_state["ihale_index_sayfa"] = sayfa
    baslangic = (sayfa - 1) * sayfa_boyutu
    parca = filtre.iloc[baslangic:baslangic + sayfa_boyutu]
    if parca.empty:
        st.info("Bu filtrelerle eşleşen resmî ihale bulunamadı.")
        return
    ihale_indeksi_goster(
        parca, toplam=len(filtre), sayfa=sayfa, sayfa_sayisi=sayfa_sayisi
    )
    geri, sayfa_bilgisi, ileri = st.columns([1, 3, 1])
    if geri.button("← Önceki", disabled=sayfa <= 1, width="stretch"):
        st.session_state["ihale_index_sayfa"] = sayfa - 1
        st.rerun()
    sayfa_bilgisi.markdown(
        f"<div style='text-align:center;padding:10px;font-weight:900'>"
        f"Sayfa {sayfa} / {sayfa_sayisi}</div>",
        unsafe_allow_html=True,
    )
    if ileri.button("Sonraki →", disabled=sayfa >= sayfa_sayisi, width="stretch"):
        st.session_state["ihale_index_sayfa"] = sayfa + 1
        st.rerun()


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
    st.subheader("İllere Göre İhale Sayısı Grafiği")
    figur = px.bar(
        il_sayilari.sort_values("İhale"), x="İhale", y="il", orientation="h",
        labels={"il": "İl"}, color="İhale",
        color_continuous_scale=["#fff176", "#ffd21f", "#d71920"],
        title=None,
    )
    figur.update_layout(coloraxis_showscale=False, margin={"l": 0, "r": 0, "t": 55, "b": 0})
    st.plotly_chart(figur, width="stretch", config={"displaylogo": False})
    tekrarlar = tekrar_ihale_ozeti(veri)
    st.subheader("Tekrarlayan Okul İhaleleri Tablosu")
    st.caption("Aynı okul için yayın ve ihale tarihleri farklı olan tekrarlar gösterilir.")
    if tekrarlar.empty:
        st.success("Seçili dönemde tekrarlayan okul ihalesi bulunmadı.")
    else:
        st.dataframe(tekrarlar, width="stretch", hide_index=True)


def _deger_var(deger: object) -> bool:
    return deger is not None and not pd.isna(deger) and bool(str(deger).strip())


def _para_bicimlendir(deger: object) -> str:
    if not _deger_var(deger):
        return "—"
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return "—"
    return f"{sayi:,.2f} TL".replace(",", "_").replace(".", ",").replace("_", ".")


def _sayi_bicimlendir(deger: object, birim: str = "") -> str:
    if not _deger_var(deger):
        return "—"
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return "—"
    metin = f"{sayi:,.0f}".replace(",", ".") if sayi.is_integer() else str(sayi)
    return f"{metin} {birim}".strip()


def yapay_zeka_analiz_sayfasi(df: pd.DataFrame) -> None:
    st.title("Yapay Zekâ İhale Analizi")
    st.caption(
        "Yalnız doğrulanmış resmî belge verileriyle aylık ve yıllık yatırım analizi."
    )
    ilan_parametresi = str(st.query_params.get("ilan", "")).strip()
    secili_id = None
    if ilan_parametresi:
        try:
            secili_id = int(ilan_parametresi)
        except ValueError:
            secili_id = None

    gorunen = df[df["analize_hazir"]].copy()
    if secili_id is not None:
        gorunen = gorunen[gorunen["ilan_id"] == secili_id]
        st.link_button(
            "← Tüm analiz kartlarına dön",
            "?sayfa=yapay-zeka-analizi",
        )
        if gorunen.empty:
            st.warning("Bu ilan son bir yıllık görünümde bulunamadı veya başka bir kayda birleştirildi.")
            return
    else:
        with st.container(key="ai_analiz_filtreleri"):
            f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
            arama = f1.text_input(
                "Kartlarda ara", placeholder="Okul, ilçe veya MEB kaynağı"
            ).strip()
            durum = f2.selectbox("Durum", ["Tümü", "Aktif", "Pasif", "Tarih incelemede"])
            il = f3.selectbox("İl", ["Tüm Türkiye"] + sorted(df["il"].dropna().unique()))
            siralama = f4.selectbox("Sıralama", ["En yeni", "En yakın ihale"])
        if arama:
            alan = (
                gorunen["okul_adi"].fillna("") + " " + gorunen["baslik"].fillna("")
                + " " + gorunen["il"].fillna("") + " " + gorunen["ilce"].fillna("")
                + " " + gorunen["kaynak"].fillna("")
            )
            gorunen = gorunen[alan.str.contains(arama, case=False, regex=False)]
        durum_kodu = {
            "Aktif": "aktif", "Pasif": "pasif", "Tarih incelemede": "tarih_bekleniyor"
        }
        if durum in durum_kodu:
            gorunen = gorunen[gorunen["durum"] == durum_kodu[durum]]
        if il != "Tüm Türkiye":
            gorunen = gorunen[gorunen["il"] == il]
        gorunen["_durum_onceligi"] = gorunen["durum"].map(
            {"aktif": 0, "pasif": 1, "tarih_bekleniyor": 2}
        ).fillna(3)
        tarih_kolonu = (
            "ihale_tarihi" if siralama == "En yakın ihale" else "yayin_tarihi"
        )
        gorunen = gorunen.sort_values(
            ["_durum_onceligi", tarih_kolonu],
            ascending=[True, siralama == "En yakın ihale"],
            na_position="last",
        )

    if gorunen.empty:
        st.info("Bu filtrelerle eşleşen analiz kartı bulunamadı.")
        return

    toplam = len(gorunen)
    sayfa_boyutu = 12
    sayfa = 1
    sayfa_sayisi = 1
    if secili_id is None and toplam > sayfa_boyutu:
        sayfa_sayisi = (toplam + sayfa_boyutu - 1) // sayfa_boyutu
        sayfa = max(1, min(int(st.session_state.get("ai_kart_sayfasi", 1)), sayfa_sayisi))
        st.session_state["ai_kart_sayfasi"] = sayfa
    baslangic = (sayfa - 1) * sayfa_boyutu
    kart_verisi = gorunen.iloc[baslangic:baslangic + sayfa_boyutu]
    st.caption(f"{toplam} ilan kartı · Yalnız zorunlu alanları doğrulanmış kayıtlar")

    kart_kolonlari = st.columns(2)
    for sira, (_, satir) in enumerate(kart_verisi.iterrows()):
        ilan_id = int(satir["ilan_id"])
        analiz = ilan_kart_analizi(satir)
        with kart_kolonlari[sira % 2]:
            with st.container(key=f"ai_ilan_karti_{ilan_id}"):
                st.html(
                    "<div class='ihalex-ai-kicker'>"
                    + html.escape(str(satir["durum_etiketi"]))
                    + " · " + html.escape(str(analiz["etiket"]))
                    + "</div><div class='ihalex-ai-school'>"
                    + html.escape(str(satir["okul_adi"]))
                    + "</div><div class='ihalex-ai-meta'>"
                    + html.escape(str(satir["il"])) + " · "
                    + html.escape(str(satir["ilce"])) + " · "
                    + html.escape(str(satir["kaynak"])) + "</div>"
                )
                temel_metrikler = [
                    ("Okul türü", str(satir["okul_turu"])),
                    ("Öğrenci", _sayi_bicimlendir(satir["ogrenci_sayisi"])),
                ]
                if _deger_var(satir.get("personel_sayisi")):
                    temel_metrikler.append(
                        ("Personel", _sayi_bicimlendir(satir["personel_sayisi"]))
                    )
                if _deger_var(satir.get("kantin_alani_m2")):
                    temel_metrikler.append((
                        "Kantin alanı", _sayi_bicimlendir(satir["kantin_alani_m2"], "m²")
                    ))
                for kolon, (etiket, deger) in zip(
                    st.columns(len(temel_metrikler)), temel_metrikler
                ):
                    kolon.metric(etiket, deger)
                ucret_metrikleri = [
                    ("Muhammen başlangıç bedeli", _para_bicimlendir(satir["muhammen_bedel_aylik"])),
                    ("Yıllık muhammen bedel", _para_bicimlendir(satir["muhammen_bedel_yillik"])),
                ]
                for alan, etiket in (
                    ("sartname_bedeli", "Şartname bedeli"),
                    ("gecici_teminat", "Geçici teminat"),
                ):
                    if _deger_var(satir.get(alan)):
                        ucret_metrikleri.append((etiket, _para_bicimlendir(satir[alan])))
                for kolon, (etiket, deger) in zip(
                    st.columns(len(ucret_metrikleri)), ucret_metrikleri
                ):
                    kolon.metric(etiket, deger)
                if _deger_var(satir.get("kira_suresi_ay")):
                    st.caption(
                        "Kira süresi · "
                        + _sayi_bicimlendir(satir["kira_suresi_ay"], "ay")
                    )
                yayin = satir["yayin_tarihi"].strftime("%d.%m.%Y")
                ihale = satir["ihale_tarihi"].strftime("%d.%m.%Y")
                st.caption(
                    f"İlan: {yayin} · İhale: {ihale} · "
                    f"Yerel belge: {int(satir.get('belge_sayisi') or 0)}"
                )
                bolge_kaynagi = str(satir.get("bolge_veri_kaynagi") or "Henüz bağlanmadı")
                bolge_durumu = (
                    "Nötr varsayım" if bolge_kaynagi == "Henüz bağlanmadı" else "Kaynak bağlı"
                )
                if bolge_kaynagi == "Henüz bağlanmadı":
                    bolge_kaynagi = "Sistem varsayımı"
                st.markdown("**Bölgesel Veri Durumu**")
                bolge1, bolge2, bolge3 = st.columns(3)
                bolge1.caption(f"Bölge verisi\n\n{bolge_durumu}")
                bolge2.caption(
                    f"Ekonomik katsayı\n\n{float(satir.get('ekonomik_katsayi') or 1):.2f}"
                )
                bolge3.caption(f"Veri kaynağı\n\n{bolge_kaynagi}")
                okul_turu_anahtari = okul_tipi_belirle(satir.get("okul_turu"))
                harcama_katsayisi = OKUL_TURU_HARCAMA_KATSAYILARI.get(
                    okul_turu_anahtari
                )
                donusum_orani = (
                    float(satir["ogrenci_donusum_orani"])
                    if _deger_var(satir.get("ogrenci_donusum_orani"))
                    else OKUL_TURU_DONUSUM_ORANLARI.get(okul_turu_anahtari)
                )
                donusum_araligi = OKUL_TURU_DONUSUM_ARALIKLARI.get(
                    okul_turu_anahtari
                )
                st.markdown("**Okul Türü Harcama Kapasitesi**")
                if harcama_katsayisi is None:
                    st.caption("Okul türü doğrulandıktan sonra öğrenci harcama katsayısı hesaplanacak.")
                else:
                    baz_harcama = 100.0
                    st.caption(
                        f"{satir['okul_turu']} öğrencileri · Katsayı ×{harcama_katsayisi:.2f} · "
                        f"Baz {baz_harcama:.2f} TL → katsayılı {baz_harcama * harcama_katsayisi:.2f} TL"
                    )
                    if donusum_orani is not None and donusum_araligi is not None:
                        st.caption(
                            "Kantinden alışveriş oranı · "
                            f"%{donusum_orani * 100:.2f} kullanılan oran "
                            f"(%{donusum_araligi[0] * 100:.0f}–"
                            f"%{donusum_araligi[1] * 100:.0f} model aralığı)"
                        )
                analiz_anahtari = f"ai_analiz_sonucu_{ilan_id}"
                hata_anahtari = f"ai_analiz_hatasi_{ilan_id}"
                yatirim_raporu = st.session_state.get(analiz_anahtari)
                if not isinstance(yatirim_raporu, dict) and _deger_var(
                    satir.get("yatirim_raporu_json")
                ):
                    try:
                        yatirim_raporu = json.loads(str(satir["yatirim_raporu_json"]))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        yatirim_raporu = None
                if st.button(
                    "Analizi yeniden hesapla" if isinstance(yatirim_raporu, dict)
                    else "Yapay zekâ ile analiz et",
                    type="primary",
                    width="stretch",
                    key=f"ai_analiz_dugmesi_{ilan_id}",
                ):
                    try:
                        yatirim_raporu = aday_analiz_raporu_olustur(ilan_id)
                        analizi_kaydet(ilan_id, yatirim_raporu)
                    except AnalizVerisiHatasi as hata:
                        st.session_state[hata_anahtari] = str(hata)
                        st.session_state.pop(analiz_anahtari, None)
                        yatirim_raporu = None
                    except Exception:
                        logging.exception("Yatırım analizi hesaplanamadı: ilan=%s", ilan_id)
                        st.session_state[hata_anahtari] = (
                            "Beklenmeyen hesaplama hatası kaydedildi; yönetim logu kontrol edilmeli."
                        )
                        st.session_state.pop(analiz_anahtari, None)
                        yatirim_raporu = None
                    else:
                        st.session_state[analiz_anahtari] = yatirim_raporu
                        st.session_state.pop(hata_anahtari, None)
                        st.session_state[f"ai_analiz_basarili_{ilan_id}"] = True
                if st.session_state.pop(f"ai_analiz_basarili_{ilan_id}", False):
                    st.success("Analiz güncel girdilerle yeniden hesaplandı ve veritabanına kaydedildi.")
                if st.session_state.get(hata_anahtari):
                    st.warning(
                        "Belgedeki zorunlu alanlar yeniden işleniyor: "
                        + str(st.session_state[hata_anahtari])
                    )
                if isinstance(yatirim_raporu, dict):
                    aylik_ciro = yatirim_raporu.get(
                        "tahmini_aylik_ciro", yatirim_raporu.get("tahmini_ciro", 0)
                    )
                    yillik_egitim_gunu = int(
                        yatirim_raporu.get("varsayimlar", {}).get(
                            "yillik_egitim_gunu", 180
                        )
                    )
                    gunluk_ciro = yatirim_raporu.get("ciro_detayi", {}).get(
                        "tahmini_gunluk_ciro", float(aylik_ciro or 0) / 20
                    )
                    yillik_ciro = yatirim_raporu.get(
                        "tahmini_yillik_ciro",
                        float(gunluk_ciro or 0) * yillik_egitim_gunu,
                    )
                    gider_detayi = yatirim_raporu.get("gider_detayi", {})
                    azami_kira_sonrasi_kar = float(
                        yatirim_raporu.get(
                            "azami_kira_sonrasi_net_kar",
                            float(aylik_ciro or 0)
                            - float(gider_detayi.get("kira_haric_gider", 0))
                            - float(yatirim_raporu.get("maksimum_kira", 0)),
                        )
                    )
                    azami_kira_sonrasi_marj = float(
                        yatirim_raporu.get(
                            "azami_kira_sonrasi_net_kar_marji",
                            azami_kira_sonrasi_kar / float(aylik_ciro or 1) * 100,
                        )
                    )
                    tahmini_ihale_orani = float(
                        yatirim_raporu.get(
                            "tahmini_ihale_azami_orani",
                            yatirim_raporu.get("varsayimlar", {}).get(
                                "tahmini_ihale_azami_orani", 0.80
                            ),
                        )
                    )
                    tahmini_ihale_kirasi = float(
                        yatirim_raporu.get(
                            "tahmini_ihale_sonucu_kira",
                            max(
                                float(satir.get("muhammen_bedel_aylik") or 0),
                                float(yatirim_raporu.get("maksimum_kira", 0))
                                * tahmini_ihale_orani,
                            ),
                        )
                    )
                    tahmini_ihale_net_kar = float(
                        yatirim_raporu.get(
                            "tahmini_ihale_sonrasi_net_kar",
                            yatirim_raporu.get("net_kar", 0),
                        )
                    )
                    tahmini_ihale_net_marj = float(
                        yatirim_raporu.get(
                            "tahmini_ihale_sonrasi_net_kar_marji",
                            tahmini_ihale_net_kar / float(aylik_ciro or 1) * 100,
                        )
                    )
                    y1, y2, y3 = st.columns(3)
                    y1.metric("Yatırım skoru", f"{int(yatirim_raporu['yatirim_skoru'])}/100")
                    y2.metric("Risk", str(yatirim_raporu["risk"]))
                    y3.metric(
                        "Tahmini ihale kirası / ciro",
                        f"%{float(yatirim_raporu['kira_orani']):.1f}",
                    )
                    skor_bilesenleri = yatirim_raporu.get(
                        "yatirim_skoru_detayi", {}
                    ).get("bilesenler", {})
                    if skor_bilesenleri:
                        st.caption(
                            "Skor hesabı · "
                            f"{float(skor_bilesenleri.get('taban_puan', 0)):+.0f} taban · "
                            f"{float(skor_bilesenleri.get('kar_marji_puani', 0)):+.0f} kâr · "
                            f"{float(skor_bilesenleri.get('kira_ciro_puani', 0)):+.0f} kira/ciro · "
                            f"{float(skor_bilesenleri.get('ogrenci_puani', 0)):+.0f} öğrenci · "
                            f"{float(skor_bilesenleri.get('bolge_puani', 0)):+.1f} bölge · "
                            f"{float(skor_bilesenleri.get('risk_kesintisi', 0)):+.1f} risk"
                        )
                    z1, z2 = st.columns(2)
                    z1.metric(
                        "Tahmini aylık ciro",
                        _para_bicimlendir(aylik_ciro),
                    )
                    z2.metric(
                        "Tahmini yıllık ciro",
                        _para_bicimlendir(yillik_ciro),
                    )
                    z3, z4 = st.columns(2)
                    z3.metric(
                        "Tahmini ihale sonucu kira",
                        _para_bicimlendir(tahmini_ihale_kirasi),
                        delta=f"Azami kiranın %{tahmini_ihale_orani * 100:.0f}'i",
                        delta_color="off",
                    )
                    z4.metric(
                        "Tahmini ihale sonrası net kâr",
                        _para_bicimlendir(tahmini_ihale_net_kar),
                        delta=f"%{tahmini_ihale_net_marj:.1f} net kâr marjı",
                        delta_color="off",
                    )
                    z5, z6 = st.columns(2)
                    z5.metric(
                        "Önerilen azami kira",
                        _para_bicimlendir(yatirim_raporu["maksimum_kira"]),
                    )
                    z6.metric(
                        "Azami kira sonrası net kâr",
                        _para_bicimlendir(azami_kira_sonrasi_kar),
                        delta=f"%{azami_kira_sonrasi_marj:.1f} net kâr marjı",
                        delta_color="off",
                    )
                    st.caption(
                        "Yatırım skoru; muhammen başlangıç bedeli yerine, önerilen "
                        f"azami kiranın %{tahmini_ihale_orani * 100:.0f}'i olarak "
                        "modellenen ihale sonucu kira üzerinden hesaplanır. Tahmin, "
                        "muhammen başlangıç bedelinden düşük olamaz."
                    )
                    st.caption(
                        "Yıllık ciro; hafta sonu, ara tatil, sömestr, yaz tatili ve "
                        "resmî tatiller hariç "
                        f"{yillik_egitim_gunu} "
                        "fiilî eğitim günü üzerinden hesaplanır."
                    )
                    st.caption(
                        "Önerilen azami kira, "
                        f"%{float(yatirim_raporu['varsayimlar']['hedef_net_kar_orani']) * 100:.0f} "
                        "hedef net kâr korunarak hesaplanır."
                    )
                    personel_raporu = yatirim_raporu.get(
                        "personel_maliyet_analizi", {}
                    )
                    if personel_raporu:
                        st.markdown("**Kantin Çalışan ve Personel Maliyeti**")
                        p1, p2 = st.columns(2)
                        p1.metric(
                            "Maliyette kullanılan çalışan",
                            int(personel_raporu["kullanilan_calisan_sayisi"]),
                        )
                        p2.metric(
                            "Toplam aylık personel",
                            _para_bicimlendir(
                                personel_raporu["toplam_personel_gideri"]
                            ),
                        )
                        st.caption(
                            f"{float(personel_raporu['aylik_calisma_saati']):.0f} "
                            "saat/çalışan · net maaş + SGK "
                            f"{_para_bicimlendir(personel_raporu['net_maas_sgk_toplami'])} · "
                            f"kişi başı {_para_bicimlendir(personel_raporu['kisi_basi_personel_maliyeti'])} · "
                            f"{personel_raporu['personel_hesaplama_modu']}"
                        )
                    okul_analizi = yatirim_raporu.get("okul_turu_analizi", {})
                    if okul_analizi:
                        st.caption(
                            "Öğrenci harcama katsayısı: "
                            f"×{float(okul_analizi['ogrenci_harcama_katsayisi']):.2f} · "
                            "Katsayılı günlük öğrenci harcaması: "
                            f"{float(okul_analizi['katsayili_ogrenci_harcamasi']):.2f} TL"
                        )
                    st.html(
                        "<div class='ihalex-ai-result'><strong>"
                        + html.escape(f"Yatırım skoru {yatirim_raporu['yatirim_skoru']}/100")
                        + "</strong><br>" + html.escape(str(yatirim_raporu["yorum"])) + "</div>"
                    )
                    st.progress(
                        int(analiz["takip_onceligi"]) / 100,
                        text=f"Takip önceliği %{int(analiz['takip_onceligi'])} · Veri güveni %{int(analiz['veri_guveni'])}",
                    )
                    st.caption(
                        str(yatirim_raporu["uyari"])
                    )
                if resmi_meb_url(str(satir["ihale_url"])):
                    st.link_button(
                        "Resmî MEB belgesini aç",
                        str(satir["ihale_url"]),
                        width="stretch",
                    )
    if secili_id is None and sayfa_sayisi > 1:
        onceki, gosterge, sonraki = st.columns([1, 1.2, 1])
        if onceki.button(
            "← Önceki",
            disabled=sayfa <= 1,
            width="stretch",
            key="ai_onceki_sayfa",
        ):
            st.session_state["ai_kart_sayfasi"] = sayfa - 1
            st.rerun()
        gosterge.markdown(
            f"<div style='text-align:center;font-weight:900;padding:.65rem'>"
            f"{sayfa} / {sayfa_sayisi}</div>",
            unsafe_allow_html=True,
        )
        if sonraki.button(
            "Sonraki →",
            disabled=sayfa >= sayfa_sayisi,
            width="stretch",
            key="ai_sonraki_sayfa",
        ):
            st.session_state["ai_kart_sayfasi"] = sayfa + 1
            st.rerun()


def _admin_cerezi_yaz(token: str, azami_saniye: int) -> None:
    guvenli_token = json.dumps(str(token))
    guvenli_ad = json.dumps(ADMIN_CEREZ_ADI)
    components.html(
        f"""
        <script>
        const ad = {guvenli_ad};
        const token = {guvenli_token};
        document.cookie = `${{ad}}=${{token}}; Max-Age={int(azami_saniye)}; Path=/; SameSite=Strict`;
        </script>
        """,
        height=0,
        width=0,
    )


def _admin_oturumunu_temizle() -> None:
    for anahtar in (
        "admin_yetkili", "admin_kullanici", "admin_oturum_bitis", "admin_oturum_tokeni"
    ):
        st.session_state.pop(anahtar, None)


def admin_giris_yapildi() -> bool:
    if st.session_state.get("admin_yetkili"):
        bitis_ham = str(st.session_state.get("admin_oturum_bitis") or "")
        if admin_oturumu_gecerli(bitis_ham):
            return True
        _admin_oturumunu_temizle()
        st.info("Üç saatlik yönetici oturumu sona erdi. Lütfen yeniden giriş yapın.")

    cerez_tokeni = str(st.context.cookies.get(ADMIN_CEREZ_ADI, ""))
    cerez_bilgisi = admin_oturum_tokenini_dogrula(cerez_tokeni)
    if cerez_bilgisi:
        st.session_state["admin_yetkili"] = True
        st.session_state["admin_kullanici"] = str(cerez_bilgisi["kullanici_adi"])
        st.session_state["admin_oturum_bitis"] = cerez_bilgisi[
            "bitis_zamani"
        ].isoformat(timespec="seconds")
        st.session_state["admin_oturum_tokeni"] = cerez_tokeni
        return True

    with st.container(key="admin_giris_karti"):
        if admin_kurulumu_gerekli():
            st.subheader("İlk yönetici hesabını oluştur")
            st.caption(
                "Bu işlem yalnızca ilk yerel kurulumda gösterilir. Parolanız şifreli özet olarak saklanır."
            )
            with st.form("ilk_admin_kurulumu", clear_on_submit=True):
                kullanici_adi = st.text_input("Kullanıcı adı", value="admin")
                parola = st.text_input("Parola", type="password")
                parola_tekrar = st.text_input("Parola tekrar", type="password")
                olustur = st.form_submit_button("Yönetici hesabını oluştur", type="primary")
            if olustur:
                if parola != parola_tekrar:
                    st.error("Parolalar eşleşmiyor.")
                else:
                    try:
                        yerel_admin_olustur(kullanici_adi, parola)
                    except AdminKimlikHatasi as hata:
                        st.error(str(hata))
                    else:
                        st.success("Yönetici hesabı oluşturuldu. Şimdi giriş yapabilirsiniz.")
                        st.rerun()
            return False

        st.subheader("Yönetici girişi")
        st.caption("Tarama, Telegram ve kaynak yönetimi için oturum açın.")
        with st.form("admin_giris", clear_on_submit=True):
            kullanici_adi = st.text_input("Kullanıcı adı", autocomplete="username")
            parola = st.text_input(
                "Parola", type="password", autocomplete="current-password"
            )
            giris = st.form_submit_button("Giriş yap", type="primary")
        if giris:
            if admin_kimligini_dogrula(kullanici_adi, parola):
                token, bitis = admin_oturum_tokeni_olustur(kullanici_adi)
                st.session_state["admin_yetkili"] = True
                st.session_state["admin_kullanici"] = kullanici_adi
                st.session_state["admin_oturum_bitis"] = bitis.isoformat(timespec="seconds")
                st.session_state["admin_oturum_tokeni"] = token
                _admin_cerezi_yaz(token, int(ADMIN_OTURUM_SURESI.total_seconds()))
                st.success("Giriş başarılı. Bu tarayıcıda oturum 3 saat açık kalacak.")
                return True
            else:
                st.error("Kullanıcı adı veya parola hatalı.")
    return False


def tarama_kontrol_paneli() -> None:
    durum = tarama_durumu_oku()
    kod = str(durum.get("durum") or "bekliyor")
    istek_bekliyor = manuel_tarama_istegi_var()
    tarama_aktif = kod in {"tariyor", "sonuclaniyor"}
    toplam = max(int(durum.get("kaynak_sayisi") or 0), 0)
    tamamlanan = max(int(durum.get("tamamlanan_kaynak") or 0), 0)
    yeni = max(
        int(durum.get("anlik_yeni_kayit") or durum.get("son_yeni_kayit") or 0),
        0,
    )
    hatalar = max(int(durum.get("hata_sayisi") or 0), 0)

    with st.container(key="admin_tarama_kontrolu"):
        st.subheader("MEB kaynak taraması")
        sol, sag = st.columns([1, 2])
        baslat = sol.button(
            "Manuel taramayı başlat",
            type="primary",
            width="stretch",
            disabled=tarama_aktif or istek_bekliyor,
        )
        if baslat:
            if manuel_tarama_iste():
                st.success("Tam tarama isteği worker'a gönderildi.")
            else:
                st.info("Bekleyen bir manuel tarama isteği zaten var.")
            st.rerun()

        if tarama_aktif:
            oran = min(tamamlanan / toplam, 1.0) if toplam else 0.0
            asama = "Sonuçlar işleniyor" if kod == "sonuclaniyor" else "Kaynaklar taranıyor"
            sag.progress(
                oran,
                text=f"{asama} · {tamamlanan}/{toplam} kaynak · {yeni} yeni",
            )
        elif istek_bekliyor:
            sag.progress(0, text="Manuel tarama sırada · worker bekleniyor")
        elif kod == "hata":
            sag.error(f"Son tarama tamamlanamadı: {durum.get('hata') or 'Bilinmeyen hata'}")
        else:
            sag.progress(1.0, text=f"Son tarama tamamlandı · {yeni} yeni ilan")

        b1, b2, b3 = st.columns(3)
        b1.metric("İşlenen kaynak", f"{tamamlanan}/{toplam}" if toplam else "—")
        b2.metric("Yeni ilan", yeni)
        b3.metric("Kaynak hatası", hatalar)
        son_bitis = str(durum.get("son_bitis") or "—").replace("T", " ")
        sonraki = str(durum.get("sonraki_tarama") or "—").replace("T", " ")
        tetikleyici = "Manuel" if durum.get("tetikleyici") == "manuel" else "Planlı"
        st.caption(
            f"Son bitiş: {son_bitis} · Son tarama: {tetikleyici} · "
            f"Sonraki planlı tarama: {sonraki}"
        )

    yenileme_araligi = 2_000 if tarama_aktif or istek_bekliyor else 5_000
    st_autorefresh(
        interval=yenileme_araligi,
        limit=None,
        key="admin_tarama_ilerleme",
    )


def belge_arsiv_durumu_goster() -> None:
    ozet = arsiv_ozeti()
    tamam = ozet["analiz_edildi"]
    toplam = tamam + ozet["bekleyen"]
    st.subheader("Yerel İhale Belge Arşivi")
    st.progress(
        tamam / max(toplam, 1),
        text=f"{tamam}/{toplam} resmî belge zorunlu alanlarıyla analiz edildi",
    )
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("Analiz edildi", ozet["analiz_edildi"])
    a2.metric("Yeniden işlenecek", ozet["analiz_bekliyor"])
    a3.metric("Sadece arşivlendi", ozet["arsivlendi"])
    a4.metric("Bekleyen", ozet["bekleyen"])
    a5.metric("Hatalı", ozet["hata"])
    st.caption(
        "Arşiv işçisi resmî MEB belgelerini kontrollü gruplar hâlinde indirir; "
        "kopyaları SHA-256 ile ayırır ve ücret alanlarını belge metninden çıkarır."
    )
    st.info(
        f"Aktif ilan zorunlu veri durumu: {ozet['aktif_hazir']} / "
        f"{ozet['aktif_toplam']} ilan analize hazır. Eksik aktif belgeler önce işlenir."
    )


@st.cache_data(ttl=30, show_spinner=False)
def meb_kaynak_listesi_getir() -> pd.DataFrame:
    try:
        with sqlite3.connect(DB) as conn:
            veri = pd.read_sql_query("""
                SELECT kurum_adi AS kurum, il, COALESCE(ilce, '') AS ilce,
                       url, kaynak_seviyesi, tarama_stratejisi,
                       dogrulandi, aktif, son_durum, son_tarama,
                       son_basarili_tarama, COALESCE(son_hata, '') AS son_hata
                FROM kaynaklar
                ORDER BY il, ilce, kurum_adi
            """, conn)
    except (sqlite3.Error, pd.errors.DatabaseError):
        logging.exception("MEB kaynak listesi okunamadı")
        return pd.DataFrame()
    if veri.empty:
        return veri
    veri["resmi_meb"] = veri["url"].map(resmi_meb_url)
    veri["dogrulama"] = veri["dogrulandi"].map({1: "Doğrulandı", 0: "Bekliyor"})
    veri["aktiflik"] = veri["aktif"].map({1: "Aktif", 0: "Kapalı"})
    veri["ilce"] = veri["ilce"].replace("", "Merkez / il kaynağı")
    veri["son_hata"] = veri["son_hata"].str.slice(0, 240)
    return veri


@st.cache_data(ttl=30, show_spinner=False)
def taranan_okul_verileri_getir() -> pd.DataFrame:
    try:
        with sqlite3.connect(DB) as conn:
            return pd.read_sql_query("""
                SELECT okul_adi, okul_turu, il, ilce,
                       ogrenci_sayisi, personel_sayisi,
                       muhammen_bedel_aylik, muhammen_bedel_yillik,
                       yayin_tarihi, ihale_tarihi, durum,
                       analize_hazir, belge_url
                FROM ihale_analiz_kayitlari
                ORDER BY CASE durum WHEN 'aktif' THEN 0 ELSE 1 END,
                         yayin_tarihi DESC, aday_id DESC
            """, conn)
    except (sqlite3.Error, pd.errors.DatabaseError):
        logging.exception("Taranan okul verileri okunamadı")
        return pd.DataFrame()


def meb_kaynak_listesi_goster() -> None:
    st.subheader("İl / İlçe MEB Kaynak Listesi")
    st.caption(
        "Worker'ın taradığı kayıtlı resmî adreslerin salt okunur görünümüdür. "
        "Bu geçici panel tarama yapısını değiştirmez."
    )
    veri = meb_kaynak_listesi_getir()
    if veri.empty:
        st.info("Kayıtlı MEB kaynağı bulunamadı.")
        return
    f1, f2, f3 = st.columns([1, 1, 1])
    il = f1.selectbox("İl", ["Tüm Türkiye"] + sorted(veri["il"].dropna().unique()), key="kaynak_liste_il")
    ilceler = sorted(veri.loc[veri["il"] == il, "ilce"].unique()) if il != "Tüm Türkiye" else []
    ilce = f2.selectbox(
        "İlçe", ["Tüm ilçeler"] + ilceler,
        disabled=il == "Tüm Türkiye", key="kaynak_liste_ilce",
    )
    durum = f3.selectbox(
        "Son durum", ["Tümü", "Başarılı", "Hata", "Bekliyor"], key="kaynak_liste_durum"
    )
    gorunen = veri
    if il != "Tüm Türkiye":
        gorunen = gorunen[gorunen["il"] == il]
    if ilce != "Tüm ilçeler":
        gorunen = gorunen[gorunen["ilce"] == ilce]
    durum_kodu = {"Başarılı": "basarili", "Hata": "hata", "Bekliyor": "bekliyor"}
    if durum in durum_kodu:
        gorunen = gorunen[
            gorunen["son_durum"].fillna("bekliyor") == durum_kodu[durum]
        ]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Gösterilen kaynak", len(gorunen))
    k2.metric("Resmî MEB URL", int(gorunen["resmi_meb"].sum()))
    k3.metric("Son tarama başarılı", int((gorunen["son_durum"] == "basarili").sum()))
    k4.metric("Son tarama hatalı", int((gorunen["son_durum"] == "hata").sum()))
    tablo = gorunen.rename(columns={
        "il": "İl", "ilce": "İlçe", "kurum": "Kurum", "url": "Resmî bağlantı",
        "kaynak_seviyesi": "Seviye", "tarama_stratejisi": "Tarama stratejisi",
        "dogrulama": "Doğrulama", "aktiflik": "Aktiflik", "son_durum": "Son durum",
        "son_tarama": "Son tarama", "son_basarili_tarama": "Son başarılı tarama",
        "son_hata": "Son hata",
    })
    st.dataframe(
        tablo[[
            "İl", "İlçe", "Kurum", "Resmî bağlantı", "Seviye", "Tarama stratejisi",
            "Doğrulama", "Aktiflik", "Son durum", "Son tarama",
            "Son başarılı tarama", "Son hata",
        ]],
        width="stretch", height=650, hide_index=True,
        column_config={
            "Resmî bağlantı": st.column_config.LinkColumn(display_text="MEB sayfasını aç"),
        },
    )
    st.divider()
    st.subheader("Taranan Okul ve İhale Verileri")
    st.caption(
        "Belge analizi tamamlandıkça okul adı, okul türü, öğrenci sayısı ve "
        "aylık/yıllık muhammen bedel kalıcı olarak veritabanında tutulur."
    )
    okullar = taranan_okul_verileri_getir()
    if okullar.empty:
        st.info("Henüz belge alanları çıkarılmış okul kaydı bulunmuyor.")
        return
    okul_gorunumu = okullar.copy()
    okul_gorunumu["analize_hazir"] = okul_gorunumu["analize_hazir"].map(
        {1: "Hazır", 0: "Yeniden işlenecek"}
    )
    okul_gorunumu = okul_gorunumu.rename(columns={
        "okul_adi": "Okul adı", "okul_turu": "Okul türü", "il": "İl",
        "ilce": "İlçe", "ogrenci_sayisi": "Öğrenci", "personel_sayisi": "Personel",
        "muhammen_bedel_aylik": "Aylık muhammen", "muhammen_bedel_yillik": "Yıllık muhammen",
        "yayin_tarihi": "Yayın tarihi", "ihale_tarihi": "İhale tarihi",
        "durum": "Durum", "analize_hazir": "Veri durumu", "belge_url": "Belge",
    })
    st.dataframe(
        okul_gorunumu,
        width="stretch", height=520, hide_index=True,
        column_config={
            "Aylık muhammen": st.column_config.NumberColumn(format="%.2f TL"),
            "Yıllık muhammen": st.column_config.NumberColumn(format="%.2f TL"),
            "Belge": st.column_config.LinkColumn(display_text="Resmî belgeyi aç"),
        },
    )


@st.cache_data(ttl=30, show_spinner=False)
def ai_yonetim_verileri_getir() -> pd.DataFrame:
    # Kamusal sayfadaki mantıksal ilan kimliklerini kullan: detay sayfası ve ek
    # dosya aynı ihaleyi temsil ettiğinde yönetimde ikinci bir satır oluşmasın.
    # Analiz kaydı olmayan aktif ilanlar ise manuel tamamlama için mutlaka kalsın.
    kamusal_veri = veri_getir()
    if kamusal_veri.empty:
        return pd.DataFrame()
    kamusal_adaylar = set(
        pd.to_numeric(kamusal_veri["ilan_id"], errors="coerce").dropna().astype(int)
    )
    try:
        with sqlite3.connect(DB) as conn:
            veri = pd.read_sql_query("""
                SELECT d.id AS aday_id, d.baslik, d.durum,
                       d.yayin_tarihi, d.ihale_tarihi,
                       COALESCE(NULLIF(TRIM(m.il), ''), k.il) AS il,
                       COALESCE(NULLIF(TRIM(m.ilce), ''), k.ilce, '') AS ilce,
                       COALESCE(
                           (SELECT b.url
                              FROM ihale_belgeleri b
                             WHERE b.aday_id=d.id
                               AND NULLIF(TRIM(b.url), '') IS NOT NULL
                             ORDER BY CASE b.durum
                                          WHEN 'analiz_edildi' THEN 0
                                          WHEN 'arsivlendi' THEN 1
                                          ELSE 2
                                      END,
                                      b.id DESC
                             LIMIT 1),
                           CASE WHEN LOWER(COALESCE(d.url, '')) LIKE '%meb_iys_dosyalar%'
                                THEN NULLIF(TRIM(d.url), '') END
                       ) AS resmi_belge_url,
                       CASE
                           WHEN LOWER(COALESCE(d.detay_url, '')) LIKE '%/www/%/icerik/%'
                               THEN d.detay_url
                           WHEN LOWER(COALESCE(d.url, '')) LIKE '%/www/%/icerik/%'
                               THEN d.url
                           ELSE COALESCE(NULLIF(TRIM(d.liste_url), ''), k.url)
                       END AS duyuru_sayfasi_url,
                       a.okul_adi AS belge_okul_adi, a.okul_turu AS belge_okul_turu,
                       a.ogrenci_sayisi AS belge_ogrenci_sayisi,
                       a.personel_sayisi AS belge_personel_sayisi,
                       a.muhammen_bedel_aylik AS belge_muhammen_aylik,
                       COALESCE(NULLIF(TRIM(m.okul_adi), ''), a.okul_adi) AS okul_adi,
                       COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu) AS okul_turu,
                       COALESCE(m.ogrenci_sayisi, a.ogrenci_sayisi) AS ogrenci_sayisi,
                       COALESCE(m.personel_sayisi, a.personel_sayisi, 0) AS personel_sayisi,
                       COALESCE(m.muhammen_bedel_aylik, a.muhammen_bedel_aylik)
                           AS muhammen_bedel_aylik,
                       COALESCE(m.muhammen_bedel_yillik, a.muhammen_bedel_yillik)
                           AS muhammen_bedel_yillik,
                       COALESCE(
                           m.ogrenci_donusum_orani,
                           CASE
                               WHEN LOWER(REPLACE(
                                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                                   'İ', 'i'
                               )) LIKE '%ilkokul%' THEN 0.36
                               WHEN LOWER(REPLACE(
                                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                                   'İ', 'i'
                               )) LIKE '%ortaokul%' THEN 0.54
                               WHEN LOWER(REPLACE(
                                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                                   'İ', 'i'
                               )) LIKE '%meslek%lise%' THEN 0.72
                               WHEN LOWER(REPLACE(
                                   COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu),
                                   'İ', 'i'
                               )) LIKE '%lise%' THEN 0.6525
                               ELSE 0.54
                           END
                       ) AS ogrenci_donusum_orani,
                       COALESCE(m.ortalama_ogrenci_harcamasi, 100.0)
                           AS ortalama_ogrenci_harcamasi,
                       COALESCE(m.ortalama_ogrenci_harcamasi, 100.0) *
                       CASE LOWER(COALESCE(NULLIF(TRIM(m.okul_turu), ''), a.okul_turu))
                           WHEN 'ilkokul' THEN 0.80
                           WHEN 'lise' THEN 1.20
                           WHEN 'meslek lisesi' THEN 1.20
                           ELSE 1.00
                       END AS gunluk_ogrenci_harcamasi,
                       COALESCE(m.yillik_egitim_gunu, 180) AS yillik_egitim_gunu,
                       COALESCE(m.hedef_net_kar_orani, 0.25) * 100
                           AS hedef_net_kar_yuzde,
                       COALESCE(m.tahmini_ihale_azami_orani, 0.80) * 100
                           AS tahmini_ihale_azami_yuzde,
                       COALESCE(m.otomatik_personel_hesapla, 1)
                           AS otomatik_personel_hesapla,
                       m.manuel_calisan_sayisi,
                       COALESCE(m.asgari_ucret, 33030.0) AS asgari_ucret,
                       COALESCE(m.net_asgari_ucret, 28075.5) AS net_asgari_ucret,
                       COALESCE(m.brut_maas, 33030.0) AS brut_maas,
                       COALESCE(m.aylik_calisma_saati, 120.0)
                           AS aylik_calisma_saati,
                       COALESCE(m.tam_zamanli_aylik_saat, 225.0)
                           AS tam_zamanli_aylik_saat,
                       COALESCE(m.sgk_isveren_orani, 0.2175) * 100
                           AS sgk_isveren_yuzde,
                       COALESCE(m.issizlik_isveren_orani, 0.02) * 100
                           AS issizlik_isveren_yuzde,
                       COALESCE(m.yemek_maliyeti, 0) AS yemek_maliyeti,
                       COALESCE(m.yol_maliyeti, 0) AS yol_maliyeti,
                       COALESCE(m.diger_yan_haklar, 0) AS diger_yan_haklar,
                       COALESCE(m.duzeltme_notu, '') AS duzeltme_notu,
                       CASE
                           WHEN m.aday_id IS NOT NULL THEN 'Manuel'
                           WHEN a.aday_id IS NOT NULL THEN 'Belge'
                           ELSE 'Manuel görev'
                       END AS veri_kaynagi,
                       y.tahmini_aylik_ciro, y.tahmini_yillik_ciro,
                       y.tahmini_net_kar,
                       y.kira_ciro_orani, y.risk_skoru, y.risk_seviyesi,
                       y.yatirim_skoru, y.maksimum_teklif,
                       y.tahmini_ihale_sonucu_kira,
                       y.tahmini_ihale_sonrasi_net_kar,
                       y.tahmini_ihale_sonrasi_net_kar_marji,
                       y.azami_kira_sonrasi_net_kar,
                       y.azami_kira_sonrasi_net_kar_marji,
                       y.baz_personel_sayisi, y.onerilen_calisan_sayisi,
                       CASE WHEN y.personel_hesaplama_modu='manuel'
                            THEN y.manuel_calisan_sayisi
                            ELSE y.onerilen_calisan_sayisi
                       END AS kullanilan_calisan_sayisi,
                       y.kisi_basi_personel_maliyeti,
                       y.net_maas_sgk_toplami,
                       y.toplam_personel_gideri, y.personel_hesaplama_modu,
                       y.sonuc_json AS rapor_json
                FROM duyuru_adaylari d
                JOIN kaynaklar k ON k.id=d.kaynak_id
                LEFT JOIN ilan_analiz_verileri a ON a.aday_id=d.id
                LEFT JOIN analiz_manuel_duzeltmeleri m ON m.aday_id=d.id
                LEFT JOIN kantin_yatirim_analizleri y ON y.aday_id=d.id
                WHERE d.yayin_tarihi >= ? OR d.durum='aktif'
                ORDER BY CASE d.durum WHEN 'aktif' THEN 0 ELSE 1 END,
                         d.yayin_tarihi DESC, d.id DESC
            """, conn, params=(ihale_tarih_siniri().isoformat(),))
        return veri[veri["aday_id"].isin(kamusal_adaylar)].reset_index(drop=True)
    except (sqlite3.Error, pd.errors.DatabaseError):
        logging.exception("AI yönetim verileri okunamadı")
        return pd.DataFrame()


def _editor_degeri_esit(sol: object, sag: object) -> bool:
    if pd.isna(sol) and pd.isna(sag):
        return True
    try:
        return abs(float(sol) - float(sag)) < 0.000001
    except (TypeError, ValueError):
        return str(sol or "").strip() == str(sag or "").strip()


def _zorunlu_alan_durumlarini_ekle(veri: pd.DataFrame) -> pd.DataFrame:
    """Yönetim tablosunda zorunlu alanların doluluk durumunu görünür kıl."""
    sonuc = veri.copy()
    il_tam = sonuc["il"].fillna("").astype(str).str.strip().ne("")
    ilce_tam = sonuc["ilce"].fillna("").astype(str).str.strip().ne("")
    okul_adi_tam = sonuc["okul_adi"].fillna("").astype(str).str.strip().ne("")
    okul_turu_tam = sonuc["okul_turu"].fillna("").astype(str).str.strip().ne("")
    ogrenci_tam = pd.to_numeric(
        sonuc["ogrenci_sayisi"], errors="coerce"
    ).fillna(0).gt(0)
    muhammen_tam = pd.to_numeric(
        sonuc["muhammen_bedel_aylik"], errors="coerce"
    ).fillna(0).gt(0)
    tumu_tam = (
        il_tam & ilce_tam & okul_adi_tam & okul_turu_tam & ogrenci_tam
        & muhammen_tam
    )

    sonuc.insert(1, "zorunlu_alan_durumu", tumu_tam.map({
        True: "🟢 Tamam",
        False: "🔴 Eksik",
    }))
    kontroller = (
        ("il_kontrol", il_tam),
        ("ilce_kontrol", ilce_tam),
        ("okul_adi_kontrol", okul_adi_tam),
        ("okul_turu_kontrol", okul_turu_tam),
        ("ogrenci_kontrol", ogrenci_tam),
        ("muhammen_kontrol", muhammen_tam),
    )
    for kolon, kontrol in kontroller:
        sonuc[kolon] = kontrol.map({True: "🟢", False: "🔴"})
    sonuc["eksik_alanlar"] = [
        ", ".join(
            alan
            for alan, dolu in (
                ("İl", il_tam.iloc[sira]),
                ("İlçe", ilce_tam.iloc[sira]),
                ("Okul adı", okul_adi_tam.iloc[sira]),
                ("Okul türü", okul_turu_tam.iloc[sira]),
                ("Öğrenci", ogrenci_tam.iloc[sira]),
                ("Aylık muhammen", muhammen_tam.iloc[sira]),
            )
            if not dolu
        )
        for sira in range(len(sonuc))
    ]
    sonuc["resmi_belge_url"] = sonuc["resmi_belge_url"].where(
        sonuc["resmi_belge_url"].map(resmi_meb_url), None
    )
    sonuc["duyuru_sayfasi_url"] = sonuc["duyuru_sayfasi_url"].where(
        sonuc["duyuru_sayfasi_url"].map(resmi_meb_url), None
    )
    return sonuc


def ai_analiz_yonetimi_goster() -> None:
    st.subheader("AI Analiz Hesaplama ve Müdahale Tablosu")
    st.caption(
        "🟢 zorunlu alan dolu, 🔴 tamamlanması gerekiyor. Sarı sütunlar yönetici "
        "girdisidir. Resmî MEB belgesi doğrudan satırdan açılır. Kaydetme işlemi "
        "belge verisini değiştirmez; ayrı düzeltme ve denetim geçmişi oluşturup "
        "tüm matematiği yeniden hesaplar. Belge ve duyuru sayfası ayrı "
        "bağlantılarla doğrulanabilir."
    )
    veri = ai_yonetim_verileri_getir()
    if veri.empty:
        st.info("Yönetilecek analiz kaydı bulunamadı.")
        return
    veri = _zorunlu_alan_durumlarini_ekle(veri)
    aktif_mi = veri["durum"].eq("aktif")
    tamam_mi = veri["zorunlu_alan_durumu"].eq("🟢 Tamam")
    o1, o2, o3 = st.columns(3)
    o1.metric("Aktif mantıksal ilan", int(aktif_mi.sum()))
    o2.metric("Aktif ve analize hazır", int((aktif_mi & tamam_mi).sum()))
    o3.metric("Aktif ve tamamlanacak", int((aktif_mi & ~tamam_mi).sum()))
    gorevler = veri[aktif_mi & ~tamam_mi].copy()
    if not gorevler.empty:
        gorevler["ihale_tarihi"] = pd.to_datetime(
            gorevler["ihale_tarihi"], errors="coerce"
        )
        gorevler = gorevler.sort_values(
            ["ihale_tarihi", "aday_id"], na_position="last"
        )
        ilk_gorev = gorevler.iloc[0]
        tarih = ilk_gorev["ihale_tarihi"]
        tarih_metni = (
            tarih.strftime("%d.%m.%Y") if pd.notna(tarih) else "Tarih doğrulanacak"
        )
        st.markdown(
            f"""
            <a href="#ai-mudahale-tablosu" style="text-decoration:none;color:inherit;">
              <div style="background:#111111;border:2px solid #D71920;border-left:10px solid #FFD21F;
                          border-radius:12px;padding:13px 16px;margin:10px 0 18px;display:flex;
                          align-items:center;gap:16px;box-shadow:0 7px 20px rgba(17,17,17,.15);">
                <span style="background:#D71920;color:white;font-weight:900;font-size:.72rem;
                             letter-spacing:.08em;padding:6px 9px;border-radius:6px;white-space:nowrap;">
                  MANUEL KONTROL HATIRLATICISI
                </span>
                <span style="color:white;flex:1;font-size:.9rem;line-height:1.35;">
                  <strong style="color:#FFD21F;font-size:1.08rem;">{len(gorevler)} açık görev</strong>
                  · En yakın: #{int(ilk_gorev['aday_id'])} · {html.escape(tarih_metni)}<br>
                  <span style="color:#d6d6d6;">Eksik: {html.escape(str(ilk_gorev['eksik_alanlar']))}</span>
                </span>
                <span style="color:#FFD21F;font-weight:900;white-space:nowrap;">Müdahale tablosuna git ↓</span>
              </div>
            </a>
            """,
            unsafe_allow_html=True,
        )
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    arama = f1.text_input(
        "Analiz tablosunda ara", placeholder="Okul, il veya ilçe", key="ai_yonetim_ara"
    ).strip()
    durum = f2.selectbox(
        "İlan durumu", ["Tümü", "Aktif", "Pasif", "Tarih incelemede"],
        index=1,
        key="ai_yonetim_durum",
    )
    kaynak = f3.selectbox(
        "Veri kaynağı", ["Tümü", "Belge", "Manuel", "Manuel görev"],
        key="ai_yonetim_kaynak"
    )
    tamamlananlari_goster = f4.toggle(
        "Tamamlananları göster",
        value=False,
        key="ai_yonetim_tamamlananlar",
        help="Kapalıyken müdahale tablosunda yalnız zorunlu alanı eksik kayıtlar görünür.",
    )
    gorunen = veri.copy()
    if arama:
        arama_alani = (
            gorunen["okul_adi"].fillna("") + " " + gorunen["il"].fillna("")
            + " " + gorunen["ilce"].fillna("")
        )
        gorunen = gorunen[arama_alani.str.contains(arama, case=False, regex=False)]
    durum_kodu = {
        "Aktif": "aktif", "Pasif": "pasif", "Tarih incelemede": "tarih_bekleniyor"
    }
    if durum in durum_kodu:
        gorunen = gorunen[gorunen["durum"] == durum_kodu[durum]]
    if kaynak != "Tümü":
        gorunen = gorunen[gorunen["veri_kaynagi"] == kaynak]
    if not tamamlananlari_goster:
        gorunen = gorunen[gorunen["zorunlu_alan_durumu"] == "🔴 Eksik"]
    if gorunen.empty:
        st.info("Bu filtrelerle eşleşen analiz kaydı yok.")
        return

    editor_kolonlari = [
        "aday_id", "zorunlu_alan_durumu", "durum",
        "il_kontrol", "il", "ilce_kontrol", "ilce",
        "resmi_belge_url", "duyuru_sayfasi_url", "veri_kaynagi",
        "okul_adi_kontrol", "okul_adi",
        "okul_turu_kontrol", "okul_turu",
        "ogrenci_kontrol", "ogrenci_sayisi", "personel_sayisi",
        "muhammen_kontrol", "muhammen_bedel_aylik", "muhammen_bedel_yillik",
        "ogrenci_donusum_orani", "gunluk_ogrenci_harcamasi",
        "yillik_egitim_gunu", "hedef_net_kar_yuzde",
        "tahmini_ihale_azami_yuzde", "duzeltme_notu",
        "otomatik_personel_hesapla", "manuel_calisan_sayisi",
        "asgari_ucret", "net_asgari_ucret", "brut_maas",
        "aylik_calisma_saati", "tam_zamanli_aylik_saat",
        "sgk_isveren_yuzde",
        "issizlik_isveren_yuzde", "yemek_maliyeti", "yol_maliyeti",
        "diger_yan_haklar",
        "tahmini_aylik_ciro", "tahmini_yillik_ciro",
        "kullanilan_calisan_sayisi",
        "kisi_basi_personel_maliyeti", "net_maas_sgk_toplami",
        "toplam_personel_gideri",
        "personel_hesaplama_modu",
        "tahmini_net_kar", "kira_ciro_orani",
        "risk_skoru", "risk_seviyesi", "yatirim_skoru", "maksimum_teklif",
        "tahmini_ihale_sonucu_kira", "tahmini_ihale_sonrasi_net_kar",
        "tahmini_ihale_sonrasi_net_kar_marji",
        "azami_kira_sonrasi_net_kar", "azami_kira_sonrasi_net_kar_marji",
    ]
    st.markdown('<div id="ai-mudahale-tablosu"></div>', unsafe_allow_html=True)
    duzenlenen = st.data_editor(
        gorunen[editor_kolonlari],
        width="stretch", height=620, hide_index=True, num_rows="fixed",
        disabled=[
            "aday_id", "zorunlu_alan_durumu", "durum",
            "resmi_belge_url", "duyuru_sayfasi_url", "veri_kaynagi",
            "il_kontrol", "ilce_kontrol", "okul_adi_kontrol",
            "okul_turu_kontrol", "ogrenci_kontrol",
            "muhammen_kontrol",
            "muhammen_bedel_yillik", "tahmini_aylik_ciro",
            "tahmini_yillik_ciro", "tahmini_net_kar",
            "kullanilan_calisan_sayisi",
            "kisi_basi_personel_maliyeti", "toplam_personel_gideri",
            "net_maas_sgk_toplami",
            "personel_hesaplama_modu",
            "kira_ciro_orani", "risk_skoru", "risk_seviyesi",
            "yatirim_skoru", "maksimum_teklif",
            "tahmini_ihale_sonucu_kira", "tahmini_ihale_sonrasi_net_kar",
            "tahmini_ihale_sonrasi_net_kar_marji",
            "azami_kira_sonrasi_net_kar", "azami_kira_sonrasi_net_kar_marji",
        ],
        column_config={
            "aday_id": st.column_config.NumberColumn("Kayıt", format="%d"),
            "zorunlu_alan_durumu": st.column_config.TextColumn(
                "Zorunlu alanlar",
                help="Tüm zorunlu alanlar doluysa yeşil; tamamlanması gereken alan varsa kırmızı.",
            ),
            "durum": "Durum",
            "il_kontrol": st.column_config.TextColumn("İl"),
            "il": st.column_config.SelectboxColumn(
                "İl", options=IL_ADLARI, required=True,
            ),
            "ilce_kontrol": st.column_config.TextColumn("İlçe"),
            "ilce": st.column_config.TextColumn("İlçe", required=True),
            "resmi_belge_url": st.column_config.LinkColumn(
                "Resmî MEB belgesi",
                display_text="Belgeyi aç",
                help="Yalnızca meb.gov.tr alan adındaki resmî kaynaklar gösterilir.",
            ),
            "duyuru_sayfasi_url": st.column_config.LinkColumn(
                "MEB duyuru sayfası",
                display_text="Duyuruyu aç",
                help="Belgenin yayımlandığı resmî MEB duyuru veya duyuru listesi.",
            ),
            "veri_kaynagi": "Girdi kaynağı",
            "okul_adi_kontrol": st.column_config.TextColumn("Ad"),
            "okul_adi": st.column_config.TextColumn("Okul adı", required=True),
            "okul_turu_kontrol": st.column_config.TextColumn("Tür"),
            "okul_turu": st.column_config.SelectboxColumn(
                "Okul türü",
                options=["İlkokul", "Ortaokul", "Lise", "Meslek Lisesi", "Karma"],
                required=True,
            ),
            "ogrenci_sayisi": st.column_config.NumberColumn(
                "Öğrenci", min_value=1, step=1, format="%d", required=True,
            ),
            "ogrenci_kontrol": st.column_config.TextColumn("Öğrenci"),
            "personel_sayisi": st.column_config.NumberColumn(
                "Personel", min_value=0, step=1, format="%d",
            ),
            "muhammen_bedel_aylik": st.column_config.NumberColumn(
                "Aylık muhammen", min_value=0.01, step=100.0, format="%.2f TL", required=True,
            ),
            "muhammen_kontrol": st.column_config.TextColumn("Muhammen"),
            "muhammen_bedel_yillik": st.column_config.NumberColumn(
                "Yıllık muhammen", format="%.2f TL",
            ),
            "ogrenci_donusum_orani": st.column_config.NumberColumn(
                "Öğrenci dönüşüm oranı", min_value=0.0, max_value=1.0,
                step=0.01, format="%.2f",
            ),
            "gunluk_ogrenci_harcamasi": st.column_config.NumberColumn(
                "Günlük öğrenci harcaması", min_value=0.01,
                step=1.0, format="%.2f TL",
            ),
            "yillik_egitim_gunu": st.column_config.NumberColumn(
                "Yıllık eğitim günü", min_value=1, max_value=366,
                step=1, format="%d", required=True,
            ),
            "hedef_net_kar_yuzde": st.column_config.NumberColumn(
                "Hedef net kâr %", min_value=0.0, max_value=100.0,
                step=1.0, format="%.1f", required=True,
            ),
            "tahmini_ihale_azami_yuzde": st.column_config.NumberColumn(
                "Tahmini ihale / azami kira %", min_value=0.0,
                max_value=100.0, step=1.0, format="%.1f", required=True,
                help="Yatırım skoru için ihale sonucunun önerilen azami kiraya yaklaşma varsayımı.",
            ),
            "otomatik_personel_hesapla": st.column_config.CheckboxColumn(
                "Otomatik personel", default=True,
            ),
            "manuel_calisan_sayisi": st.column_config.NumberColumn(
                "Manuel çalışan", min_value=1, step=1, format="%d",
            ),
            "asgari_ucret": st.column_config.NumberColumn(
                "Asgari ücret", min_value=0.01, step=100.0, format="%.2f TL",
            ),
            "net_asgari_ucret": st.column_config.NumberColumn(
                "Net asgari ücret", min_value=0.01, step=100.0, format="%.2f TL",
            ),
            "brut_maas": st.column_config.NumberColumn(
                "Tam zamanlı brüt referans", min_value=0.01,
                step=100.0, format="%.2f TL",
            ),
            "aylik_calisma_saati": st.column_config.NumberColumn(
                "Part-time saat/ay", min_value=1.0, max_value=225.0,
                step=1.0, format="%.0f",
            ),
            "tam_zamanli_aylik_saat": st.column_config.NumberColumn(
                "Tam zamanlı saat/ay", min_value=1.0,
                step=1.0, format="%.0f",
            ),
            "sgk_isveren_yuzde": st.column_config.NumberColumn(
                "SGK işveren %", min_value=0.0, max_value=100.0,
                step=0.25, format="%.2f",
            ),
            "issizlik_isveren_yuzde": st.column_config.NumberColumn(
                "İşsizlik işveren %", min_value=0.0, max_value=100.0,
                step=0.25, format="%.2f",
            ),
            "yemek_maliyeti": st.column_config.NumberColumn(
                "Yemek/kişi", min_value=0.0, step=100.0, format="%.2f TL",
            ),
            "yol_maliyeti": st.column_config.NumberColumn(
                "Yol/kişi", min_value=0.0, step=100.0, format="%.2f TL",
            ),
            "diger_yan_haklar": st.column_config.NumberColumn(
                "Diğer yan hak/kişi", min_value=0.0, step=100.0, format="%.2f TL",
            ),
            "duzeltme_notu": st.column_config.TextColumn("Düzeltme notu"),
            "tahmini_aylik_ciro": st.column_config.NumberColumn("Aylık tahmini ciro", format="%.2f TL"),
            "tahmini_yillik_ciro": st.column_config.NumberColumn("Yıllık tahmini ciro", format="%.2f TL"),
            "kullanilan_calisan_sayisi": st.column_config.NumberColumn("Maliyette kullanılan çalışan", format="%d"),
            "kisi_basi_personel_maliyeti": st.column_config.NumberColumn("Kişi başı maliyet", format="%.2f TL"),
            "net_maas_sgk_toplami": st.column_config.NumberColumn("Net maaş + SGK", format="%.2f TL"),
            "toplam_personel_gideri": st.column_config.NumberColumn("Toplam personel", format="%.2f TL"),
            "personel_hesaplama_modu": "Personel modu",
            "tahmini_net_kar": st.column_config.NumberColumn("Net kâr", format="%.2f TL"),
            "kira_ciro_orani": st.column_config.NumberColumn("Kira/ciro %", format="%.2f"),
            "risk_skoru": st.column_config.NumberColumn("Risk puanı", format="%.2f"),
            "risk_seviyesi": "Risk", "yatirim_skoru": "Yatırım skoru",
            "maksimum_teklif": st.column_config.NumberColumn("Azami teklif", format="%.2f TL"),
            "tahmini_ihale_sonucu_kira": st.column_config.NumberColumn(
                "Tahmini ihale sonucu kira", format="%.2f TL"
            ),
            "tahmini_ihale_sonrasi_net_kar": st.column_config.NumberColumn(
                "İhale sonucu net kâr", format="%.2f TL"
            ),
            "tahmini_ihale_sonrasi_net_kar_marji": st.column_config.NumberColumn(
                "İhale sonucu net kâr %", format="%.2f"
            ),
            "azami_kira_sonrasi_net_kar": st.column_config.NumberColumn(
                "Azami kira sonrası net kâr", format="%.2f TL"
            ),
            "azami_kira_sonrasi_net_kar_marji": st.column_config.NumberColumn(
                "Azami kira sonrası net kâr %", format="%.2f"
            ),
        },
        key="ai_hesaplama_editoru",
    )
    kaydet, geri_al = st.columns([1, 1])
    if kaydet.button("Değişiklikleri kaydet ve yeniden hesapla", type="primary", width="stretch"):
        temel = gorunen.set_index("aday_id")
        degisen = 0
        hatalar: list[str] = []
        giris_alanlari = [
            "il", "ilce", "okul_adi", "okul_turu",
            "ogrenci_sayisi", "personel_sayisi",
            "muhammen_bedel_aylik", "ogrenci_donusum_orani",
            "gunluk_ogrenci_harcamasi", "yillik_egitim_gunu",
            "hedef_net_kar_yuzde", "tahmini_ihale_azami_yuzde",
            "duzeltme_notu",
            "otomatik_personel_hesapla", "manuel_calisan_sayisi",
            "asgari_ucret", "net_asgari_ucret", "brut_maas",
            "aylik_calisma_saati", "tam_zamanli_aylik_saat",
            "sgk_isveren_yuzde",
            "issizlik_isveren_yuzde", "yemek_maliyeti", "yol_maliyeti",
            "diger_yan_haklar",
        ]
        for _, satir in duzenlenen.iterrows():
            aday_id = int(satir["aday_id"])
            onceki = temel.loc[aday_id]
            if not any(
                not _editor_degeri_esit(satir[alan], onceki[alan])
                for alan in giris_alanlari
            ):
                continue
            try:
                payload = {alan: satir[alan] for alan in giris_alanlari}
                tur_anahtari = okul_tipi_belirle(payload["okul_turu"])
                harcama_katsayisi = OKUL_TURU_HARCAMA_KATSAYILARI.get(
                    tur_anahtari, 1.0
                )
                payload["ortalama_ogrenci_harcamasi"] = (
                    float(payload.pop("gunluk_ogrenci_harcamasi"))
                    / harcama_katsayisi
                )
                payload["hedef_net_kar_orani"] = (
                    float(payload.pop("hedef_net_kar_yuzde")) / 100
                )
                payload["tahmini_ihale_azami_orani"] = (
                    float(payload.pop("tahmini_ihale_azami_yuzde")) / 100
                )
                payload["sgk_isveren_orani"] = (
                    float(payload.pop("sgk_isveren_yuzde")) / 100
                )
                payload["issizlik_isveren_orani"] = (
                    float(payload.pop("issizlik_isveren_yuzde")) / 100
                )
                manuel_duzeltme_kaydet(
                    aday_id,
                    payload,
                    duzelten=str(st.session_state.get("admin_kullanici", "admin")),
                )
                degisen += 1
            except (AnalizVerisiHatasi, ValueError, TypeError) as hata:
                hatalar.append(f"#{aday_id}: {hata}")
        if hatalar:
            st.error("\n".join(hatalar[:10]))
        if degisen:
            st.cache_data.clear()
            st.success(f"{degisen} kayıt kaydedildi ve yeniden hesaplandı.")
            st.rerun()
        elif not hatalar:
            st.info("Kaydedilecek bir değişiklik bulunamadı.")

    manuel_kayitlar = gorunen[gorunen["veri_kaynagi"] == "Manuel"]
    geri_al_id = geri_al.selectbox(
        "Manuel düzeltmeyi geri al",
        options=[None] + manuel_kayitlar["aday_id"].astype(int).tolist(),
        format_func=lambda deger: "Kayıt seçin" if deger is None else (
            f"#{deger} · " + str(
                manuel_kayitlar.loc[manuel_kayitlar["aday_id"] == deger, "okul_adi"].iloc[0]
            )
        ),
        key="ai_duzeltme_geri_al_id",
    )
    if geri_al.button(
        "Seçili manuel düzeltmeyi kaldır", disabled=geri_al_id is None, width="stretch"
    ):
        manuel_duzeltmeyi_kaldir(
            int(geri_al_id),
            duzelten=str(st.session_state.get("admin_kullanici", "admin")),
        )
        st.cache_data.clear()
        st.success("Manuel katman kaldırıldı; belge verisi yeniden etkinleştirildi.")
        st.rerun()

    st.divider()
    st.subheader("Analizin Tam Matematiği")
    raporlu = gorunen[gorunen["rapor_json"].notna()]
    if raporlu.empty:
        st.info("Henüz matematik dökümü oluşturulmuş rapor yok.")
        return
    secili_id = st.selectbox(
        "Matematiği gösterilecek kayıt",
        options=raporlu["aday_id"].astype(int).tolist(),
        format_func=lambda deger: (
            f"#{deger} · "
            + str(raporlu.loc[raporlu["aday_id"] == deger, "okul_adi"].iloc[0])
        ),
        key="ai_matematik_kaydi",
    )
    secili = raporlu.loc[raporlu["aday_id"] == secili_id].iloc[0]
    try:
        rapor = json.loads(str(secili["rapor_json"]))
    except (TypeError, ValueError, json.JSONDecodeError):
        st.error("Kayıtlı rapor JSON verisi okunamadı.")
        return
    matematik = pd.DataFrame(analiz_matematigi_olustur(rapor))
    st.dataframe(
        matematik, width="stretch", hide_index=True,
        column_config={"Sonuç": st.column_config.NumberColumn(format="%.4f")},
    )
    with st.expander("Kullanılan tüm girdiler ve varsayımlar"):
        st.json({
            "girdiler": rapor.get("girdiler", {}),
            "varsayimlar": rapor.get("varsayimlar", {}),
            "ciro_detayi": rapor.get("ciro_detayi", {}),
            "gider_detayi": rapor.get("gider_detayi", {}),
            "risk_detayi": rapor.get("risk_detayi", {}),
            "yatirim_skoru_detayi": rapor.get("yatirim_skoru_detayi", {}),
            "maksimum_teklif_detayi": rapor.get("maksimum_teklif_detayi", {}),
        })


@st.cache_data(ttl=60, show_spinner=False)
def sistem_surumleri_getir() -> pd.DataFrame:
    try:
        with sqlite3.connect(DB) as conn:
            return pd.read_sql_query("""
                SELECT surum_kodu, surum_adi, yayin_tarihi,
                       analiz_motoru_surumu, git_etiketi, aciklama
                FROM sistem_surumleri
                ORDER BY yayin_tarihi DESC, surum_kodu DESC
            """, conn)
    except (sqlite3.Error, pd.errors.DatabaseError):
        logging.exception("Sistem sürümleri okunamadı")
        return pd.DataFrame()


def surum_gecmisi_goster() -> None:
    st.subheader("İhalex Sürüm Geçmişi")
    st.success(
        f"Güncel sürüm: {GUNCEL_SURUM['surum_kodu']} · "
        f"{GUNCEL_SURUM['surum_adi']} · {GUNCEL_SURUM['yayin_tarihi']}"
    )
    st.caption(
        "Sürüm kodu tüm İhalex yapısını kapsar. Analiz motoru alt sürümü ayrıca izlenir."
    )
    surumler = sistem_surumleri_getir()
    if surumler.empty:
        st.info("Kayıtlı sürüm bulunamadı.")
        return
    st.dataframe(
        surumler.rename(columns={
            "surum_kodu": "İhalex sürümü", "surum_adi": "Sürüm adı",
            "yayin_tarihi": "Tarih", "analiz_motoru_surumu": "Analiz motoru",
            "git_etiketi": "Git etiketi", "aciklama": "Değişiklik özeti",
        }),
        width="stretch", hide_index=True,
    )


def yonetim_operasyonlari_goster() -> None:
    tarama_kontrol_paneli()
    belge_arsiv_durumu_goster()
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
        st.subheader("Telegram Abone Tablosu")
        st.dataframe(pd.DataFrame(abone_listesi), width="stretch", hide_index=True)


def yonetim_sayfasi() -> None:
    st.title("Yönetim")
    if not admin_giris_yapildi():
        return
    hesap, cikis = st.columns([4, 1])
    bitis = str(st.session_state.get("admin_oturum_bitis") or "")
    hesap.caption(
        f"Oturum: {st.session_state.get('admin_kullanici', 'yönetici')} · "
        f"3 saat geçerli · Bitiş: {bitis[11:16] if len(bitis) >= 16 else '-'}"
    )
    if cikis.button("Çıkış yap", width="stretch"):
        _admin_cerezi_yaz("", 0)
        _admin_oturumunu_temizle()
        st.success("Yönetici oturumu kapatıldı.")
        st.stop()
    operasyon, kaynaklar, analiz, surumler = st.tabs([
        "Tarama ve Telegram", "MEB Kaynak Listesi",
        "AI Analiz Hesaplama", "Sürüm Geçmişi",
    ])
    with operasyon:
        yonetim_operasyonlari_goster()
    with kaynaklar:
        meb_kaynak_listesi_goster()
    with analiz:
        ai_analiz_yonetimi_goster()
    with surumler:
        surum_gecmisi_goster()


def uygulama() -> None:
    veritabani_hazirla(VERITABANI_SEMA_SURUMU)
    gomulu = str(st.query_params.get("embedded", "0")) == "1"
    stilleri_yukle(gomulu)
    banner_foto = gorsel_data_uri(str(BANNER_GORSELI))
    st.markdown(
        f"""
        <section class="ihalex-radar-banner"
                 style="--ihalex-banner-photo: url('{banner_foto}')"
                 aria-label="İhalex, Türkiye'nin İlk Yapay Zekâ Destekli Kantin İhale Platformu">
          <div class="ihalex-radar-photo" role="img"
               aria-label="Sarı duotone okul kantini panoraması"></div>
          <div class="ihalex-radar-brand" role="img" aria-label="İHALEX">
            <h1><span class="i-letter">I</span>HALE<span class="x">X</span></h1>
          </div>
          <div class="ihalex-radar-copy">
            <small>OKUL KANTİNİ İHALE AĞI</small>
            <strong>Türkiye’nin İlk Yapay Zekâ Destekli Kantin İhale Platformu</strong>
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
    navigasyon_varsayilani = (
        None if "ana_navigasyon" in st.session_state else varsayilan
    )
    secim = st.segmented_control(
        "Ana menü", list(SAYFALAR), default=navigasyon_varsayilani,
        label_visibility="collapsed", key="ana_navigasyon",
    )
    sayfa = SAYFALAR.get(secim or "Ana Sayfa", "ana-sayfa")
    if sayfa != istenen:
        st.query_params["sayfa"] = sayfa
        st.session_state["_ihalex_sayfa_parametresi"] = sayfa
    if sayfa != "yapay-zeka-analizi":
        st.query_params.pop("ilan", None)
    df = veri_getir()
    kamusal_df = df[df["kamusal_hazir"]].copy() if not df.empty else df
    if df.empty:
        st.warning("Son bir yıl içinde doğrulanmış ihale verisi bulunamadı.")
    elif sayfa == "ana-sayfa":
        ana_sayfa(kamusal_df)
    elif sayfa == "ihaleler":
        ihaleler_sayfasi(kamusal_df, gomulu)
    elif sayfa == "istatistikler":
        istatistik_sayfasi(kamusal_df)
    elif sayfa == "yapay-zeka-analizi":
        yapay_zeka_analiz_sayfasi(df)
    else:
        yonetim_sayfasi()
    st.markdown(
        "<div class='ihalex-footer'>İhalex · Resmî MEB kaynakları · "
        "Veriler 60 saniyede yenilenir · "
        f"{GUNCEL_SURUM['surum_kodu']} · {GUNCEL_SURUM['surum_adi']} · "
        "İhalex, MEB veya ilan.gov.tr'nin resmî sitesi değildir.</div>",
        unsafe_allow_html=True,
    )
    st_autorefresh(interval=60_000, limit=None, key="site_yenileme")


uygulama()
