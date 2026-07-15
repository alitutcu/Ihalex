from pdf2image import convert_from_path
import pytesseract

# Tesseract yolu
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pdf_dosya = "ilanlar/ornek_ihale.pdf"

print("PDF görüntüye çevriliyor...")

sayfalar = convert_from_path(
    pdf_dosya,
    poppler_path=r"C:\poppler\Library\bin"
)

metin = ""

for i, sayfa in enumerate(sayfalar):
    print(f"{i+1}. sayfa okunuyor...")

    yazilar = pytesseract.image_to_string(
        sayfa,
        lang="tur",
        config="--psm 6"
    )

    metin += yazilar


print("\nPDF METNİ:")
print("--------------------")
print(metin)
with open("ilan_metni.txt", "w", encoding="utf-8") as dosya:
    dosya.write(metin)

print("ilan_metni.txt oluşturuldu")
dir