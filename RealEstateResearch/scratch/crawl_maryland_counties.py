import os
import re
import json
import time
import sys
from bs4 import BeautifulSoup
from curl_cffi import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RAW_DIR = r"raw"
SCRATCH_DIR = r"scratch"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)

session = requests.Session(impersonate="chrome124")

DOWNLOAD_TARGETS = [
    # Wicomico
    ("Wicomico_2026_OTC_Tax_Sale_List.pdf", "https://www.wicomicocounty.org/DocumentCenter/View/14387/2026-OVER-THE-COUNTER-LIST"),
    ("Wicomico_2026_Tax_Sale_Excess_Funds.pdf", "https://www.wicomicocounty.org/DocumentCenter/View/15843/2026-UPDATE-TAX-SALE-EXCESS-LIST-2-11-26"),
    # Queen Anne's
    ("Queen_Annes_Available_OTC_Tax_Certs.pdf", "https://www.qac.org/DocumentCenter/View/26124"),
    ("Queen_Annes_Tax_Sale_Excess_Funds.pdf", "https://www.qac.org/DocumentCenter/View/26132"),
    # Worcester
    ("Worcester_2026_OTC_Tax_Liens.pdf", "https://www.worcestermd.gov/sites/default/files/2026-05/OverTheCounter.pdf"),
    ("Worcester_2026_Excess_Proceeds_List.pdf", "https://www.worcestermd.gov/sites/default/files/2026-05/ExcessProceeds.pdf"),
    # Cecil
    ("Cecil_County_Week_4_Tax_Sale_Advertisement.pdf", "https://www.cecilcountymd.gov/DocumentCenter/View/5971"),
    ("Cecil_County_Bidder_Contract_2026.pdf", "https://www.cecilcountymd.gov/DocumentCenter/View/781"),
    # Caroline
    ("Caroline_County_2026_Tax_Sale_Results.pdf", "https://www.carolinecounty.org/DocumentCenter/View/12385/2026-TAX-SALE-RESULTS"),
    ("Caroline_County_Current_Excess_Funds_List.pdf", "https://www.carolinecounty.org/DocumentCenter/View/7812/Current-List"),
    # Howard
    ("Howard_County_Tax_Sale_Proceeds_2026.xlsx", "https://www.howardcountymd.gov/sites/default/files/2026-04/Tax%20Sale%20Proceeds%20FEB%202026.xlsx"),
    ("Howard_County_Tax_Sale_Bidder_Results.xlsx", "https://www.howardcountymd.gov/sites/default/files/2025-08/WinnerResultForPublic.xlsx"),
    # Baltimore County
    ("Baltimore_County_Tax_Sale_List.xlsx", "https://bcg-prod.baltimorecountymd.gov/files/departments/Budget%20and%20Finance/documents/taxadvertisingfile4.xlsx")
]

downloaded = []
for filename, url in DOWNLOAD_TARGETS:
    out_path = os.path.join(RAW_DIR, filename)
    print(f"Downloading: {filename} from {url}...")
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(out_path, "wb") as f:
                f.write(resp.content)
            print(f"  [SUCCESS] Saved {filename} ({len(resp.content):,} bytes)")
            downloaded.append({"file": filename, "url": url, "size": len(resp.content)})
        else:
            print(f"  [FAILED] Status {resp.status_code}, Length {len(resp.content)}")
    except Exception as e:
        print(f"  [ERROR] {e}")
    time.sleep(0.5)

print(f"\nSuccessfully downloaded {len(downloaded)} county tax sale datasets into raw/.")
