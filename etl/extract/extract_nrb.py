import requests
from bs4 import BeautifulSoup

URL = "https://www.nrb.org.np/?s=current+macroeconomic+"
HEADERS = {"User-Agent": "Mozilla/5.0"}

response = requests.get(URL, headers=HEADERS, timeout=30)
print("Status:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

for link in soup.find_all("a"):
    text = link.get_text(strip=True)
    if "Tables" in text:
        print(text)
        print("   ->", link.get("href"))