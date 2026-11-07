from curl_cffi import requests
from bs4 import BeautifulSoup

session = requests.Session(impersonate="chrome124")
url = "https://aacounty.munisselfservice.com/citizens/RealEstate/Default.aspx"

r1 = session.get(url)
soup1 = BeautifulSoup(r1.text, "html.parser")

post_data = {
    "__EVENTTARGET": "",
    "__EVENTARGUMENT": "",
    "__VIEWSTATE": soup1.find("input", {"id": "__VIEWSTATE"})["value"],
    "__VIEWSTATEGENERATOR": soup1.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
    "__EVENTVALIDATION": soup1.find("input", {"id": "__EVENTVALIDATION"})["value"],
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$AddressSearchFieldLayout$ctl01$StreetNumberTextBox": "",
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$StreetNameSearchFieldLayout$ctl01$AddressTextBox": "",
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$ParcelIdSearchFieldLayout$ctl01$ParcelIDTextBox": "474604872500",
    "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$Control$FormLayoutItem7$ctl01$Button1": "Search"
}

r2 = session.post(url, data=post_data)
soup2 = BeautifulSoup(r2.text, "html.parser")

for a in soup2.find_all("a", href=True):
    if "ViewBill" in a.text or "View" in a.text or "Bill" in a.text:
        print("Link text:", a.text.strip(), "href:", a["href"])
