import requests
import json

# Test MD iMAP Property Data MapServer
url = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"

params = {
    "where": "ADDRESS LIKE '%1883%CEDAR%' OR ACCTID = '020474690008900'",
    "outFields": "*",
    "f": "json",
    "returnGeometry": "false"
}

headers = {
    "User-Agent": "Mozilla/5.0"
}

try:
    r = requests.get(url, params=params, headers=headers, timeout=15)
    print("Status:", r.status_code)
    data = r.json()
    features = data.get("features", [])
    print(f"Found {len(features)} features")
    if features:
        print(json.dumps(features[0]["attributes"], indent=2))
except Exception as e:
    print("Error:", e)
