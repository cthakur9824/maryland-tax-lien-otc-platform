import requests
from bs4 import BeautifulSoup
import re

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

url = "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
r = session.get(url)
soup = BeautifulSoup(r.text, "html.parser")

viewstate = soup.find("input", {"id": "__VIEWSTATE"})
eventvalidation = soup.find("input", {"id": "__EVENTVALIDATION"})

print("Status:", r.status_code)
print("Title:", soup.title.string if soup.title else "No title")
print("Has ViewState:", bool(viewstate))
print("Has EventValidation:", bool(eventvalidation))

# Find form elements
counties = []
county_select = soup.find("select", {"id": re.compile(r"County", re.I)})
if county_select:
    print("County select id:", county_select.get("id"))
    for opt in county_select.find_all("option"):
        counties.append((opt.get("value"), opt.text.strip()))
    print("Counties sample:", counties[:5])

search_types = []
type_select = soup.find("select", {"id": re.compile(r"SearchType|Method", re.I)})
if type_select:
    print("Search type select id:", type_select.get("id"))
    for opt in type_select.find_all("option"):
        search_types.append((opt.get("value"), opt.text.strip()))
    print("Search types:", search_types)
