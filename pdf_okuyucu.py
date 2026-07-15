from pypdf import PdfReader

dosya = "ilanlar/ornek_ihale.pdf"

pdf = PdfReader(dosya)

metin = ""

for sayfa in pdf.pages:
    metin += sayfa.extract_text()

print("PDF OKUNDU")
print("----------------")
print(metin)