from curl_cffi import requests
from bs4 import BeautifulSoup

url = "https://sdat.dat.maryland.gov/RealProperty/Pages/viewdetails.aspx?County=02&SearchType=ACCT&District=04&AccountNumber=04872500&subDiv=746"

r = requests.get(url, impersonate="chrome124")
print("Status:", r.status_code)
if r.status_code == 200:
    soup = BeautifulSoup(r.text, "html.parser")
    print("Page Title:", soup.title.string if soup.title else "No title")
    for span in soup.find_all(id=lambda x: x and "cphMain" in x):
        txt = span.text.strip()
        if txt:
            print(f"{span.get('id')}: {txt}")
else:
    print("Failed snippet:", r.text[:300])
