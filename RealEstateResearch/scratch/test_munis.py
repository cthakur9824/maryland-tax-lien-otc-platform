import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

url = "https://aacounty.munisselfservice.com/citizens/RealEstate/Default.aspx"

r = cffi_requests.get(url, impersonate="chrome124")
print("Munis Status:", r.status_code)
if r.status_code == 200:
    soup = BeautifulSoup(r.text, "html.parser")
    print("Munis Title:", soup.title.string if soup.title else "No title")
    # check form inputs
    inputs = [i.get('name') for i in soup.find_all('input') if i.get('name')]
    print("Input names:", inputs)
