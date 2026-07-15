"""İhalex gerçek zamanlı MEB kantin ihalesi dashboardı."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from harita_gosterici import ilce_secenekleri, turkiye_haritasi
from harita_motoru import IL_ADLARI, ilce_harita_istatistikleri, ilce_istatistikleri
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


WORKER_DURUM_DOSYASI = Path(__file__).resolve().with_name("worker_durumu.json")


def worker_durumu_getir() -> dict:
    try:
        return json.loads(WORKER_DURUM_DOSYASI.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def veri_getir() -> pd.DataFrame:
    """Son bir yıldaki duyuruları, ek dosyaları tek ihale altında birleştirerek getirir."""
    sorgu = """
        WITH sirali AS (
            SELECT
                d.baslik,
                k.il,
                k.ilce,
                k.kurum_adi AS kaynak,
                d.yayin_tarihi,
                d.ihale_tarihi,
                d.durum,
                d.eslesme_turu,
                d.dosya_turu,
                COALESCE(NULLIF(d.detay_url, ''), d.url) AS ihale_url,
                d.url AS dosya_url,
                d.ilk_gorulme,
                ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(NULLIF(d.detay_url, ''), d.url)
                    ORDER BY
                        CASE d.eslesme_turu
                            WHEN 'detay' THEN 0
                            WHEN 'toplu_dosya' THEN 1
                            WHEN 'dosya' THEN 2
                            ELSE 3
                        END,
                        d.id
                ) AS sira
            FROM duyuru_adaylari d
            JOIN kaynaklar k ON k.id = d.kaynak_id
            WHERE d.yayin_tarihi >= ?
        )
        SELECT baslik, il, ilce, kaynak, yayin_tarihi, ihale_tarihi, durum,
               eslesme_turu, dosya_turu, ihale_url, dosya_url, ilk_gorulme
        FROM sirali
        WHERE sira = 1
        ORDER BY yayin_tarihi DESC, ilk_gorulme DESC
    """
    try:
        with sqlite3.connect(DB) as conn:
            df = pd.read_sql_query(sorgu, conn, params=(ihale_tarih_siniri().isoformat(),))
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()
    if not df.empty:
        df["yayin_tarihi"] = pd.to_datetime(df["yayin_tarihi"], errors="coerce")
        df["ihale_tarihi"] = pd.to_datetime(df["ihale_tarihi"], errors="coerce")
        df = df.dropna(subset=["yayin_tarihi"])
        df["ilce"] = df["ilce"].fillna("")
        df["gun"] = (pd.Timestamp(date.today()) - df["yayin_tarihi"]).dt.days.clip(lower=0)
        df["durum_etiketi"] = df["durum"].map({
            "aktif": "🟢 Aktif",
            "pasif": "⚫ Pasif",
            "tarih_bekleniyor": "🟡 Tarih bekleniyor",
        }).fillna("🟡 Tarih bekleniyor")
    return df


def tablo_goster(veri: pd.DataFrame, *, sinir: int | None = None) -> None:
    if sinir is not None:
        veri = veri.head(sinir)
    gorunum = veri.rename(columns={
        "baslik": "İhale",
        "il": "İl",
        "ilce": "İlçe",
        "kaynak": "MEB kaynağı",
        "yayin_tarihi": "Yayın tarihi",
        "ihale_tarihi": "İhale tarihi",
        "durum_etiketi": "Durum",
        "ihale_url": "Bağlantı",
    })
    gorunum["İlçe"] = gorunum["İlçe"].fillna("").replace("", "Doğrulanıyor")
    kolonlar = [
        "İhale", "İl", "İlçe", "Yayın tarihi", "İhale tarihi",
        "Durum", "MEB kaynağı", "Bağlantı",
    ]
    st.dataframe(
        gorunum[kolonlar],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Yayın tarihi": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "İhale tarihi": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "Bağlantı": st.column_config.LinkColumn(display_text="Duyuruyu aç"),
        },
    )


def istatistikleri_goster(veri: pd.DataFrame) -> None:
    """İhale dağılımı, bölgesel oran ve tekrar adaylarını gösterir."""
    if veri.empty:
        st.info("İstatistik oluşturmak için henüz yeterli ihale verisi yok.")
        return

    donem_secimi = st.selectbox(
        "İstatistik dönemi", ["Son 6 ay", "Son 1 yıl"], index=1,
        key="istatistik_donemi",
    )
    gun_sayisi = 183 if donem_secimi == "Son 6 ay" else 365
    baslangic = pd.Timestamp(date.today()) - pd.Timedelta(days=gun_sayisi)
    donem = veri[veri["yayin_tarihi"] >= baslangic].copy()
    if donem.empty:
        st.info(f"{donem_secimi} için ihale verisi bulunamadı.")
        return

    donem["İlçe"] = donem["ilce"].fillna("")
    gecerli_sureler = donem.dropna(subset=["ihale_tarihi"]).copy()
    gecerli_sureler["hazirlik_gunu"] = (
        gecerli_sureler["ihale_tarihi"] - gecerli_sureler["yayin_tarihi"]
    ).dt.days
    gecerli_sureler = gecerli_sureler[gecerli_sureler["hazirlik_gunu"] > 0]
    ortanca_hazirlik = (
        int(round(gecerli_sureler["hazirlik_gunu"].median()))
        if not gecerli_sureler.empty else 0
    )

    tekrarlar = tekrar_ihale_ozeti(donem)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"{donem_secimi} ihale", len(donem))
    m2.metric("İhale görülen il", int(donem["il"].nunique()))
    m3.metric("Tekrar adayı okul", len(tekrarlar))
    m4.metric("Ortanca hazırlık süresi", f"{ortanca_hazirlik} gün" if ortanca_hazirlik else "—")
    st.caption(
        "Oranlar seçili dönemdeki tüm Türkiye ihale toplamına göre hesaplanır. "
        "Tekrar adaylarında aynı dosyanın ekleri sayılmaz; farklı yayın ve ihale tarihi "
        "çiftleri esas alınır."
    )

    il_tablosu = (
        donem.groupby("il", as_index=False)
        .size()
        .rename(columns={"il": "İl", "size": "İhale sayısı"})
        .sort_values("İhale sayısı", ascending=False)
    )
    il_tablosu["Genel oran (%)"] = (
        il_tablosu["İhale sayısı"] / len(donem) * 100
    ).round(2)
    ilcesi_bilinmeyen = int((donem["İlçe"] == "").sum())
    ilce_tablosu = (
        donem[donem["İlçe"] != ""].groupby(["il", "İlçe"], as_index=False)
        .size()
        .rename(columns={"il": "İl", "size": "İhale sayısı"})
        .sort_values("İhale sayısı", ascending=False)
    )
    ilce_tablosu["Genel oran (%)"] = (
        ilce_tablosu["İhale sayısı"] / len(donem) * 100
    ).round(2)

    il_sekmesi, ilce_sekmesi = st.tabs(["İl bazında", "İlçe bazında"])
    with il_sekmesi:
        st.dataframe(
            il_tablosu,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Genel oran (%)": st.column_config.ProgressColumn(
                    "Türkiye payı", format="%.2f%%", min_value=0, max_value=100
                )
            },
        )
    with ilce_sekmesi:
        if ilcesi_bilinmeyen:
            st.caption(
                f"{ilcesi_bilinmeyen} ilanın ilçesi henüz resmî MEB okul dizininden "
                "doğrulanmadığı için bu tabloya dâhil edilmedi."
            )
        ilce_il_secimi = st.selectbox(
            "İl filtresi",
            ["Tüm iller"] + sorted(ilce_tablosu["İl"].dropna().unique().tolist()),
            key="istatistik_ilce_il_filtresi",
        )
        ilce_gorunumu = ilce_tablosu
        if ilce_il_secimi != "Tüm iller":
            ilce_gorunumu = ilce_gorunumu[ilce_gorunumu["İl"] == ilce_il_secimi]
        st.dataframe(
            ilce_gorunumu,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Genel oran (%)": st.column_config.ProgressColumn(
                    "Türkiye payı", format="%.2f%%", min_value=0, max_value=100
                )
            },
        )

    durum_adlari = {
        "aktif": "Aktif",
        "pasif": "Pasif",
        "tarih_bekleniyor": "Tarih bekleniyor",
    }
    grafik1, grafik2 = st.columns(2)

    durum_ozeti = (
        donem.assign(Durum=donem["durum"].map(durum_adlari).fillna("Tarih bekleniyor"))
        .groupby("Durum", as_index=False)
        .size()
        .rename(columns={"size": "İhale sayısı"})
    )
    durum_grafigi = px.pie(
        durum_ozeti,
        names="Durum",
        values="İhale sayısı",
        hole=0.48,
        title="İhaleler hangi durumda?",
        color="Durum",
        color_discrete_map={
            "Aktif": "#2EAD68",
            "Pasif": "#222222",
            "Tarih bekleniyor": "#F2C230",
        },
    )
    durum_grafigi.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="%{label}<br>%{value} ihale<br>%{percent}<extra></extra>",
    )
    durum_grafigi.add_annotation(
        text=f"Toplam<br><b>{len(donem)}</b>", showarrow=False, font_size=16
    )
    durum_grafigi.update_layout(
        height=390,
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"),
    )
    grafik1.plotly_chart(
        durum_grafigi,
        use_container_width=True,
        key="durum_istatistigi",
        config={"displayModeBar": False},
    )

    aylik_ozet = (
        donem.assign(Ay=donem["yayin_tarihi"].dt.to_period("M").astype(str))
        .groupby("Ay", as_index=False)
        .size()
        .rename(columns={"size": "Yayımlanan ihale"})
        .sort_values("Ay")
    )
    ay_tarihleri = pd.to_datetime(aylik_ozet["Ay"] + "-01")
    ay_adlari = {
        1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
        7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara",
    }
    aylik_ozet["Ay etiketi"] = [
        f"{ay_adlari[tarih.month]} {tarih.year}" for tarih in ay_tarihleri
    ]
    aylik_grafik = px.bar(
        aylik_ozet,
        x="Ay etiketi",
        y="Yayımlanan ihale",
        text="Yayımlanan ihale",
        title="Aylara göre yayımlanan ihaleler",
    )
    aylik_grafik.update_traces(
        textposition="outside",
        marker_color="#F2C230",
        marker_line_color="#222222",
        marker_line_width=1,
        hovertemplate="%{x}<br>%{y} ihale<extra></extra>",
    )
    aylik_grafik.update_layout(
        height=390,
        margin=dict(l=20, r=20, t=55, b=20),
        xaxis_title=None,
        yaxis_title="İhale sayısı",
        showlegend=False,
    )
    grafik2.plotly_chart(
        aylik_grafik,
        use_container_width=True,
        key="aylik_istatistik",
        config={"displayModeBar": False},
    )

    st.subheader("Tekrar Eden Okul Kantini İhale Adayları")
    if tekrarlar.empty:
        st.success(f"{donem_secimi} içinde aynı okul adına bağlı tekrar ihale adayı bulunmadı.")
    else:
        tekrar_gorunumu = tekrarlar.rename(columns={"il": "İl"})[
            ["Okul", "İl", "İlçe", "İhale sayısı", "Yayın tarihleri", "İhale tarihleri"]
        ]
        st.dataframe(
            tekrar_gorunumu,
            use_container_width=True,
            hide_index=True,
        )


st.set_page_config(page_title="İhalex", page_icon="📣", layout="wide")
st.image("assets/ihalex-logo-yellow.png", width="stretch")
st.markdown(
    "<h2 style='text-align:center; margin-top:-0.4rem;'>"
    "Türkiye’nin İhale Fırsat Haritası"
    "</h2>",
    unsafe_allow_html=True,
)
st.caption(
    f"Yalnızca {ihale_tarih_siniri().strftime('%d.%m.%Y')} ve sonrasında yayımlanan "
    "resmî MEB kantin ihale duyuruları gösterilir."
)
st.divider()

df = veri_getir()
kaynaklar = kaynak_ozeti()
alarmlar = alarm_ozeti()
aboneler = telegram_abone_ozeti()
ham_arsiv = ham_arsiv_ozeti()
worker_durumu = worker_durumu_getir()

if df.empty:
    st.warning("Son bir yıl içinde doğrulanmış kantin ihalesi bulunamadı.")
else:
    aktif_sayisi = int((df["durum"] == "aktif").sum())
    pasif_sayisi = int((df["durum"] == "pasif").sum())
    bekleyen_sayisi = int((df["durum"] == "tarih_bekleniyor").sum())
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Toplam İhale", len(df))
    o2.metric("Aktif İhale", aktif_sayisi)
    o3.metric("Pasif İhale", pasif_sayisi)
    o4.metric("Tarihi Beklenen", bekleyen_sayisi)

st.divider()
st.subheader("🔥 En Yeni İhale Duyuruları")
if not df.empty:
    st.caption(f"Son 1 yıllık {len(df)} ihalenin en yeni 50 kaydı gösteriliyor.")
    tablo_goster(df, sinir=50)

st.divider()
st.subheader("🗺️ Türkiye İlçe Bazlı Fırsat Haritası")
try:
    harita_df = ilce_harita_istatistikleri()
    if harita_df["ilan_sayisi"].sum() > 0:
        hf1, hf2 = st.columns(2)
        harita_il = hf1.selectbox("Harita ili", ["Tüm Türkiye"] + list(IL_ADLARI[1:]))
        ilce_listesi = ilce_secenekleri(harita_il) if harita_il != "Tüm Türkiye" else []
        harita_ilce = hf2.selectbox(
            "Harita ilçesi",
            ["Tüm ilçeler"] + ilce_listesi,
            disabled=harita_il == "Tüm Türkiye",
        )
        secilen_il = None if harita_il == "Tüm Türkiye" else harita_il
        secilen_ilce = None if harita_ilce == "Tüm ilçeler" else harita_ilce
        st.plotly_chart(
            turkiye_haritasi(harita_df, secilen_il, secilen_ilce),
            width="stretch",
            key="turkiye_firsat_haritasi",
            config={
                "responsive": True,
                "scrollZoom": False,
                "displaylogo": False,
                "doubleClick": "reset",
            },
        )
        gorunen = harita_df
        if secilen_il:
            gorunen = gorunen[gorunen["il"] == secilen_il]
        if secilen_ilce:
            gorunen = gorunen[gorunen["ilce"] == secilen_ilce]
        st.caption(
            f"Seçili görünümde {int(gorunen['ilan_sayisi'].sum())} ihale haritada gösteriliyor. "
            "İl seviyesinde toplu yayımlanan kayıtlar ana tabloda yer almaya devam eder."
        )
        if not secilen_il:
            harita_disi = max(len(df) - int(harita_df["ilan_sayisi"].sum()), 0)
            if harita_disi:
                st.caption(
                    f"{harita_disi} kayıt ilçesi henüz doğrulanmadığı için harita katmanına "
                    "dâhil değildir; üst toplam ve ana tabloda yer alır."
                )
    else:
        st.info("Harita verisi hazırlanıyor.")
except Exception as hata:
    st.error(f"Harita hatası: {hata}")

st.divider()
st.subheader("📍 İlçe Analizi")
if not df.empty:
    iller = ["Seçiniz"] + sorted(df["il"].dropna().unique().tolist())
    secilen_il = st.selectbox("İl seç", iller)
    if secilen_il != "Seçiniz":
        st.dataframe(ilce_istatistikleri(secilen_il), use_container_width=True, hide_index=True)
else:
    st.info("İlçe verisi yok.")

st.divider()
st.subheader("🎯 İhale Filtresi")
if not df.empty:
    f1, f2, f3 = st.columns(3)
    gun_siniri = f1.slider(
        "Yayın dönemi (gün)",
        1,
        365,
        365,
        key="ihale_yayin_donemi_gun_v2",
        help="Üst özet kartları son 1 yılı kapsar; aynı toplam için 365 gün seçili kalmalıdır.",
    )
    il_secimi = f2.selectbox("Bölge", ["Tüm Türkiye"] + sorted(df["il"].dropna().unique().tolist()))
    durum_secimi = f3.selectbox(
        "Durum", ["Tümü", "Aktif", "Pasif", "Tarih bekleniyor"]
    )
    filtre = df[df["gun"] <= gun_siniri]
    if il_secimi != "Tüm Türkiye":
        filtre = filtre[filtre["il"] == il_secimi]
    durum_esleme = {
        "Aktif": "aktif",
        "Pasif": "pasif",
        "Tarih bekleniyor": "tarih_bekleniyor",
    }
    if durum_secimi != "Tümü":
        filtre = filtre[filtre["durum"] == durum_esleme[durum_secimi]]
    st.caption(
        f"Seçili kapsamda {len(filtre)} ihale bulundu · "
        f"Üst kartların kapsamı: son 365 gün."
    )
    tablo_goster(filtre)

st.divider()
kapsam_sekmesi, istatistik_sekmesi, admin_sekmesi = st.tabs(
    ["📡 Kaynak Kapsamı", "📊 İstatistikler", "🔐 Admin"]
)
with kapsam_sekmesi:
    st.subheader("Türkiye MEB Kaynak Kapsamı")
    taranan_kaynak = int(kaynaklar["basarili"]) + int(kaynaklar["hata"])
    toplam_kaynak = max(int(kaynaklar["dogrulanmis"]), taranan_kaynak, 1)
    tarama_orani = min(taranan_kaynak / toplam_kaynak, 1.0)
    st.progress(
        tarama_orani,
        text=f"MEB kaynakları taranıyor · {taranan_kaynak}/{toplam_kaynak} kaynak kontrol edildi",
    )
    sonraki_tarama = worker_durumu.get("sonraki_tarama")
    if sonraki_tarama:
        try:
            sonraki_metin = datetime.fromisoformat(sonraki_tarama).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            sonraki_metin = str(sonraki_tarama)
        st.caption(
            f"Tam kaynak taraması her gün 11:59 ve 23:59'da çalışır · "
            f"Sonraki tarama: {sonraki_metin}"
        )
    else:
        st.caption("Tam kaynak taraması her gün 11:59 ve 23:59'da çalışır.")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("İl kaynağı", kaynaklar["il"])
    k2.metric("İlçe kaynağı", kaynaklar["ilce"])
    k3.metric("Başarılı kaynak", kaynaklar["basarili"])
    k4.metric("Hatalı kaynak", kaynaklar["hata"])
    st.caption(f"{kaynaklar['dogrulanmis']} doğrulanmış resmî MEB bağlantısı takip ediliyor.")
    st.caption(
        f"Son 1 yıllık ham arşiv: {ham_arsiv['toplam']} bağlantı · "
        f"Doğrulandı: {ham_arsiv['dogrulandi']} · "
        f"Bağlantı hatası: {ham_arsiv['hatali']} · "
        f"Yeniden denenecek: {ham_arsiv['bekliyor']}"
    )
    st.caption(
        f"Telegram: {'hazır' if telegram_hazir() else 'yapılandırılmadı'} · "
        f"Aktif abone: {aboneler['aktif']} · "
        f"Bekleyen: {alarmlar.get('bekliyor', 0)} · "
        f"Gönderilen: {alarmlar.get('gonderildi', 0)}"
    )

    st.subheader("🤖 Telegram Alarmları")
    telegram_baglanti_hazir = telegram_hazir()
    if not telegram_baglanti_hazir:
        st.info(
            "BotFather tokenini aşağıdaki parola alanına gir. Token yalnızca bu "
            "bilgisayarda, Windows hesabına bağlı şifreli biçimde saklanır."
        )
        with st.form("telegram_kurulum_formu", clear_on_submit=True):
            telegram_tokeni = st.text_input(
                "BotFather tokeni",
                type="password",
                placeholder="123456789:AA...",
            )
            bagla = st.form_submit_button("Botu bağla ve test et", type="primary")
        if bagla:
            try:
                with st.spinner("/start mesajı ve bot bağlantısı doğrulanıyor..."):
                    sonuc = telegram_baglantisini_kur(telegram_tokeni)
                telegram_baglanti_hazir = True
                st.success(
                    f"@{sonuc['bot']} bağlandı. Telegram'a doğrulama mesajı gönderildi."
                )
            except TelegramKurulumHatasi as hata:
                st.error(str(hata))

    if telegram_baglanti_hazir:
        st.success("Telegram bağlantısı hazır.")
        bot_baglantisi = telegram_bot_baglantisi()
        st.caption(
            "Bu botu açıp /start gönderen herkes otomatik abone olur; "
            "/stop gönderen abonelikten çıkar."
        )
        if bot_baglantisi:
            st.code(bot_baglantisi, language=None)
        tg1, tg2 = st.columns(2)
        if tg1.button("Tüm abonelere test gönder", width="stretch"):
            try:
                sonuc = telegram_test_mesaji_gonder()
                st.success(
                    f"Test mesajı {sonuc['gonderilen']} aboneye gönderildi"
                    + (f" · Hata: {sonuc['hata']}" if sonuc["hata"] else "")
                )
            except TelegramKurulumHatasi as hata:
                st.error(str(hata))
        if tg2.button("Aktif ihaleleri tüm abonelere gönder", type="primary", width="stretch"):
            aktif_ilanlari_kuyruga_al(yeniden_gonder=True)
            gonderilen = bekleyenleri_gonder(limit=1000)
            if gonderilen:
                st.success(f"{gonderilen} Telegram mesajı abonelere gönderildi.")
            else:
                st.info("Gönderilecek yeni aktif ihale bulunamadı.")

with istatistik_sekmesi:
    istatistikleri_goster(df)

with admin_sekmesi:
    st.subheader("Telegram Abone Yönetimi")
    st.caption(
        "Bu bölüm yalnızca yönetim içindir. Telegram telefon numarasını paylaşmaz; "
        "teknik hesap numarası olarak chat ID gösterilir."
    )
    if telegram_hazir():
        if st.button("Abonelikleri şimdi yenile", type="primary"):
            try:
                yenileme = telegram_aboneleri_yenile()
                st.success(
                    f"Abonelikler yenilendi · Yeni: {yenileme['eklenen']} · "
                    f"Ayrılan: {yenileme['ayrilan']}"
                )
            except TelegramKurulumHatasi as hata:
                st.error(str(hata))
        admin_ozeti = telegram_abone_ozeti()
        a1, a2 = st.columns(2)
        a1.metric("Toplam kullanıcı", admin_ozeti["toplam"])
        a2.metric("Aktif abone", admin_ozeti["aktif"])
        abone_listesi = telegram_abone_listesi()
        if abone_listesi:
            abone_tablosu = pd.DataFrame(
                [
                    {
                        "Görünen ad": x["ad"] or "Kurucu hesap",
                        "Kullanıcı adı": (
                            f"@{x['kullanici_adi']}" if x["kullanici_adi"] else "—"
                        ),
                        "Chat ID": x["chat_id"],
                        "Tür": x["sohbet_turu"],
                        "Durum": "Aktif" if x["aktif"] else "Pasif",
                        "Katılma": x["baslama_tarihi"],
                        "Son işlem": x["son_gorulme"],
                    }
                    for x in abone_listesi
                ]
            )
            st.dataframe(abone_tablosu, width="stretch", hide_index=True)
        else:
            st.info("Henüz /start gönderen kayıtlı Telegram kullanıcısı yok.")
    else:
        st.warning("Önce Telegram bot bağlantısını kurmalısın.")

st.divider()
st.caption("İhalex v1.2 · Resmî MEB kaynakları · 60 saniyede otomatik yenileme")
st_autorefresh(interval=60_000, limit=None, key="dashboard_yenileme")
