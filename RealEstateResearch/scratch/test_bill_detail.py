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

# Postback to view bill ctl02 (most recent year)
post_data2 = {
    "__EVENTTARGET": "ctl00$ctl00$PrimaryPlaceHolder$ContentPlaceHolderMain$BillsGridView$ctl02$ViewBillLinkButton",
    "__EVENTARGUMENT": "",
    "__VIEWSTATE": soup2.find("input", {"id": "__VIEWSTATE"})["value"],
    "__VIEWSTATEGENERATOR": soup2.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
    "__EVENTVALIDATION": soup2.find("input", {"id": "__EVENTVALIDATION"})["value"]
}

r3 = session.post("https://aacounty.munisselfservice.com/citizens/RealEstate/ParcelBrowse.aspx", data=post_data2)
print("Bill Page Status:", r3.status_code)
print("Bill Page URL:", r3.url)

soup3 = BeautifulSoup(r3.text, "html.parser")
for tr in soup3.find_all("tr"):
    cols = [td.text.strip() for td in tr.find_all(["th", "td"])]
    if any(cols):
        print(" | ".join(cols))

for span in soup3.find_all("span"):
    txt = span.text.strip()
    if any(k in txt.lower() for k in ["total", "due", "balance", "paid", "delinquent", "tax", "status", "$"]):
        if len(txt) < 100:
            print(f"Span ({span.get('id', 'no-id')}): {txt}")
