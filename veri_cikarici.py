import re


# OCR çıktısını oku
with open("ilan_metni.txt", "r", encoding="utf-8") as dosya:
    metin = dosya.read()


print("VERİ ÇIKARMA BAŞLADI")
print("--------------------")


# Okul adı
okul = re.search(
    r"(.+?İLKOKULU).*?OKUL KANTİNİNİN",
    metin,
    re.S
)

if okul:
    print("Okul:", okul.group(1).strip())


# Metrekare
metrekare = re.search(
    r"Yüzölçümü[:\s]+([\d,.]+)\s*m2",
    metin
)

if metrekare:
    print("Alan:", metrekare.group(1), "m2")


# Öğrenci sayısı
ogrenci = re.search(
    r"Öğrenci mevcudu\s*(\d+)",
    metin
)

if ogrenci:
    print("Öğrenci:", ogrenci.group(1))


# Personel
personel = re.search(
    r"(\d+)\s*\n?idare personel",
    metin
)

if personel:
    print("Personel:", personel.group(1))


# Muhammen bedel
bedel = re.search(
    r"Bedel:.*?([\d.]+,00)",
    metin,
    re.S
)

if bedel:
    print("Kira:", bedel.group(1),"TL")
