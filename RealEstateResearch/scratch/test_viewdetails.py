import requests
from bs4 import BeautifulSoup

url = "https://sdat.dat.maryland.gov/RealProperty/Pages/viewdetails.aspx?County=02&SearchType=ACCT&District=04&AccountNumber=04872500&subDiv=746"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

r = requests.get(url, headers=headers)
print("Status:", r.status_code)
if r.status_code == 200:
    soup = BeautifulSoup(r.text, "html.parser")
    # find owner name span
    owner = soup.find(id=lambda x: x and "OwnerName" in x)
    print("Owner element:", owner.text if owner else "None")
    # print all spans with cphMain
    for span in soup.find_all(id=lambda x: x and "cphMain" in x):
        print(f"{span.get('id')}: {span.text.strip()}")
else:
    print("Response text snippet:", r.text[:300])
