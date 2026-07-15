import pandas as pd

# İlk kantin verimiz
kantin = {
    "İl": ["Kocaeli"],
    "İlçe": ["İzmit"],
    "Okul": ["Yahya Kaptan Anadolu Lisesi"],
    "Öğrenci": [665],
    "Personel": [55],
    "Muhammen Bedel": [140000]
}

# Tablo oluştur
tablo = pd.DataFrame(kantin)

# Excel'e kaydet
tablo.to_excel("kantin_verileri.xlsx", index=False)

print("KantinRadar AI çalıştı!")
print("Excel dosyası oluşturuldu.")

