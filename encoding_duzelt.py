dosya = "turkiye_ilceler.json"


with open(
    dosya,
    "r",
    encoding="utf-8"
) as f:
    veri = f.read()



# Bozuk Türkçe karakter dönüşümleri

veri = veri.replace("Ã‡", "Ç")
veri = veri.replace("Ã§", "ç")

veri = veri.replace("Ã–", "Ö")
veri = veri.replace("Ã¶", "ö")

veri = veri.replace("Ãœ", "Ü")
veri = veri.replace("Ã¼", "ü")

veri = veri.replace("Ä°", "İ")
veri = veri.replace("Ä±", "ı")

veri = veri.replace("Åž", "Ş")
veri = veri.replace("ÅŸ", "ş")

veri = veri.replace("Äž", "Ğ")
veri = veri.replace("ÄŸ", "ğ")



with open(
    dosya,
    "w",
    encoding="utf-8"
) as f:
    f.write(veri)



print("Düzeltme tamamlandı.")