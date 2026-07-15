import json


print("KANTİNRADARAI ANALİZ MOTORU")
print("----------------------------")


# veri_cikarici çıktıları
ogrenci = 195
personel = 20
kira = 51000
alan = 57.78


# -------------------------
# 1. Müşteri potansiyeli
# -------------------------

gunluk_musteri = int(ogrenci * 0.60) + int(personel * 0.50)

print("Tahmini günlük müşteri:", gunluk_musteri)


# -------------------------
# 2. Ciro tahmini
# -------------------------

ortalama_harcama = 25

gunluk_ciro = gunluk_musteri * ortalama_harcama

aylik_ciro = gunluk_ciro * 20

donem_ciro = aylik_ciro * 8.5


print("Tahmini aylık ciro:", aylik_ciro, "TL")
print("Dönem cirosu:", int(donem_ciro), "TL")


# -------------------------
# 3. Kira oranı
# -------------------------

kira_orani = (kira / donem_ciro) * 100

print(
    "Kira/Ciro oranı:",
    round(kira_orani,2),
    "%"
)


# -------------------------
# 4. Skor hesaplama
# -------------------------

skor = 50


# öğrenci puanı

if ogrenci >= 500:
    skor += 25

elif ogrenci >= 300:
    skor += 15

elif ogrenci >= 150:
    skor += 5

else:
    skor -= 10


# kira puanı

if kira_orani < 10:
    skor += 20

elif kira_orani < 20:
    skor += 10

else:
    skor -= 15


# alan puanı

if alan >= 50:
    skor += 5

else:
    skor -= 5



# sınırlar

if skor > 100:
    skor = 100

if skor < 0:
    skor = 0



print("----------------------------")
print("KANTİN SKORU:", skor, "/100")


# karar

if skor >= 75:

    karar = "🟢 GİRİLEBİLİR"

elif skor >= 50:

    karar = "🟡 DİKKATLİ İNCELENMELİ"

else:

    karar = "🔴 RİSKLİ"


print("SONUÇ:", karar)