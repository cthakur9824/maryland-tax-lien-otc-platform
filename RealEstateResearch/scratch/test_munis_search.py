from curl_cffi import requests
from bs4 import BeautifulSoup
import urllib.parse

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
print("Search Status:", r2.status_code)
print("Search URL:", r2.url)

soup2 = BeautifulSoup(r2.text, "html.parser")
# Check table or results
table = soup2.find("table")
if table:
    print("Found table in response!")
    for row in table.find_all("tr"):
        print([td.text.strip() for td in row.find_all(["th", "td"])])
else:
    print("No table, check text snippet:")
    for a in soup2.find_all("a"):
        if "Parcel" in a.text or "Detail" in a.text or "View" in a.text or "1883" in a.text:
            print("Link:", a.text.strip(), a.get("href"))
    print(soup2.text[:500])
