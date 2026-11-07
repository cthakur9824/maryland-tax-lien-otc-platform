import requests
import json

url = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0?f=json"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
data = r.json()
fields = [f["name"] for f in data.get("fields", [])]
print("All fields count:", len(fields))
print("Fields:", fields)
