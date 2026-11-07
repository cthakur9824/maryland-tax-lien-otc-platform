import requests
import json

# Search Maryland Socrata datasets
url = "https://opendata.maryland.gov/api/views.json?q=Real%20Property"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
data = r.json()
print("Found datasets:", len(data))
for item in data[:5]:
    print(item.get("id"), "-", item.get("name"))

# Query Maryland Real Property Assessments
# Search by address or account
query_url = "https://opendata.maryland.gov/resource/ed4q-awbi.json"
r2 = requests.get(query_url, params={"$q": "1883 CEDAR", "$limit": 3}, headers={"User-Agent": "Mozilla/5.0"})
print("\nDirect Query status:", r2.status_code)
if r2.status_code == 200:
    res = r2.json()
    print(f"Results: {len(res)}")
    if res:
        print(json.dumps(res[0], indent=2))
