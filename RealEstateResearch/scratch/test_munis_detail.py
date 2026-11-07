from curl_cffi import requests
from bs4 import BeautifulSoup
import re

session = requests.Session(impersonate="chrome124")
url = "https://aacounty.munisselfservice.com/citizens/RealEstate/Default.aspx"

r1 = session.get(url)
soup1 = BeautifulSoup(r1.text, "html.parser")

viewstate = soup1.find("input", {"id": "__VIEWSTATE"})["value"]
viewstategen = soup1.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"]
eventval = soup1.find("input", {"id": "__EVENTVALIDATION"})["value"]

post_data = {
    "__EVENTTARGET": "",
    "__EVENTARGUMENT": "",
    "__VIEWSTATE": viewstate,
    "__VIEWSTATEGENERATOR": viewstategen,
    "__EVENTVALIDATION": eventval,
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$AddressSearchFieldLayout$ctl01$StreetNumberTextBox": "1883",
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$StreetNameSearchFieldLayout$ctl01$AddressTextBox": "Cedar",
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$ParcelIdSearchFieldLayout$ctl01$ParcelIDTextBox": "",
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$FormLayoutItem7$ctl01$Button1": "Search"
}

r2 = session.post(url, data=post_data)
soup2 = BeautifulSoup(r2.text, "html.parser")

# Find the link to details for each parcel
for a in soup2.find_all("a", href=True):
    if "ViewBill" in a["href"] or "Parcel" in a["href"] or "Detail" in a["href"] or "Bill" in a["href"]:
        print("Link:", a.text.strip(), a["href"])

# Let's follow the first parcel link
links = [a["href"] for a in soup2.find_all("a", href=True) if "ParcelDetail.aspx" in a["href"] or "ViewBill" in a["href"]]
if links:
    detail_url = "https://aacounty.munisselfservice.com/citizens/RealEstate/" + links[0] if not links[0].startswith("http") else links[0]
    r3 = session.get(detail_url)
    print("\n--- Detail Page ---")
    print("Detail URL:", r3.url)
    soup3 = BeautifulSoup(r3.text, "html.parser")
    for table in soup3.find_all("table"):
        for row in table.find_all("tr"):
            cols = [td.text.strip() for td in row.find_all(["th", "td"])]
            if any(cols):
                print(cols)
