import requests
from bs4 import BeautifulSoup


url = "https://www.sahibinden.com"


headers = {
    "User-Agent": 
    "Mozilla/5.0"
}


cevap = requests.get(
    url,
    headers=headers
)


print("Durum kodu:")
print(cevap.status_code)


soup = BeautifulSoup(
    cevap.text,
    "html.parser"
)


print("\nSayfa başlığı:")
print(soup.title.text)