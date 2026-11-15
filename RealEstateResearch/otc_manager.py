"""
Maryland Over-The-Counter (OTC) Tax Lien Importer & Intelligent County Web Crawler
Automatically crawls Maryland county tax sale portals for new OTC / Remaining Lien lists,
and provides a universal importer for CSV, Excel (.xlsx), PDF, and JSON county lists.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re
import csv
import io
import json
import time
import datetime
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

from sdat_engine import search_maryland_property, COUNTY_JURS_MAP
from title_search_engine import analyze_maryland_title

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "raw")
AUTO_SYNC_DIR = os.path.join(RAW_DIR, "auto_sync")
UPLOADS_DIR = os.path.join(RAW_DIR, "uploads")
SCRATCH_DIR = os.path.join(BASE_DIR, "scratch")

MASTER_JSON_PATH = os.path.join(SCRATCH_DIR, "maryland_master_otc_liens.json")
GRADED_JSON_PATH = os.path.join(SCRATCH_DIR, "otc_graded_deals.json")
AA_PARSED_JSON_PATH = os.path.join(SCRATCH_DIR, "anne_arundel_parsed_liens.json")
SYNC_STATUS_PATH = os.path.join(SCRATCH_DIR, "otc_sync_status.json")
CSV_OUTPUT_PATH = os.path.join(RAW_DIR, "Maryland_24_Counties_Tax_Lien_OTC_Master_2026.csv")
LOG_PATH = os.path.join(BASE_DIR, "log.md")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(AUTO_SYNC_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)

COUNTY_DEFAULTS = {
    "Anne Arundel County": {"code": "ANNE", "interest": "12.0% Annual (1.0% / mo)", "redemption": "6 Months", "contact": "taxsale@aacounty.org | (410) 222-1735 / financeinfo@aacounty.org | (410) 222-1144"},
    "Kent County": {"code": "KENT", "interest": "12.0% Annual (1.0% / mo)", "redemption": "6 Months", "contact": "financeinfo@kentgov.org | (410) 778-7478"},
    "Wicomico County": {"code": "WICO", "interest": "12.0% Annual (1.0% / mo)", "redemption": "6 Months", "contact": "finance@wicomicocounty.org | (410) 548-4840"},
    "Worcester County": {"code": "WORC", "interest": "12.0% Annual (1.0% / mo)", "redemption": "6 Months", "contact": "taxes@co.worcester.md.us | (410) 632-0686"},
    "Queen Anne's County": {"code": "QUEE", "interest": "10.0% Annual", "redemption": "6 Months", "contact": "treasury@qac.org | (410) 758-0414"},
    "Cecil County": {"code": "CECI", "interest": "12.0% Annual (1.0% / mo)", "redemption": "6 Months", "contact": "taxsale@cecilcountymd.gov | (410) 996-5385"},
    "Baltimore City": {"code": "BALT_CITY", "interest": "12.0% to 18.0% Annual", "redemption": "6 Months", "contact": "taxsale@baltimorecity.gov | (410) 396-3987"},
    "Baltimore County": {"code": "BALT_CO", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "finance@baltimorecountymd.gov | (410) 887-2404"},
    "Prince George's County": {"code": "PRIN", "interest": "20.0% Annual", "redemption": "6 Months", "contact": "taxsale@co.pg.md.us | (301) 952-4030"},
    "Carroll County": {"code": "CARR", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "collections@carrollcountymd.gov | (410) 386-2970"},
    "Frederick County": {"code": "FRED", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "treasurer@frederickcountymd.gov | (301) 600-1111"},
    "Howard County": {"code": "HOWA", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "taxsale@howardcountymd.gov | (410) 313-2195"},
    "Caroline County": {"code": "CARO", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "tax@carolinemd.org | (410) 479-0410"},
    "Charles County": {"code": "CHAR", "interest": "10.0% to 12.0% Annual", "redemption": "6 Months", "contact": "treasreas@charlescountymd.gov | (301) 645-0685"},
    "Harford County": {"code": "HARF", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "treasurer@harfordcountymd.gov | (410) 638-3314"},
    "Washington County": {"code": "WASH", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "treasurer@washco-md.net | (240) 313-2110"},
    "Allegany County": {"code": "ALLE", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "tax@alleganygov.org | (301) 777-5965"},
    "Calvert County": {"code": "CALV", "interest": "10.0% Annual", "redemption": "6 Months", "contact": "treasurer@calvertcountymd.gov | (410) 535-1600"},
    "Dorchester County": {"code": "DORC", "interest": "10.0% Annual", "redemption": "6 Months", "contact": "tax@docogonet.com | (410) 228-4466"},
    "Garrett County": {"code": "GARR", "interest": "10.0% Annual", "redemption": "6 Months", "contact": "tax@garrettcountymd.gov | (301) 334-1965"},
    "Montgomery County": {"code": "MONT", "interest": "20.0% Annual", "redemption": "6 Months", "contact": "taxsale@montgomerycountymd.gov | (240) 777-8950"},
    "Somerset County": {"code": "SOME", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "finance@somersetmd.us | (410) 651-0774"},
    "St. Mary's County": {"code": "STMA", "interest": "10.0% Annual", "redemption": "6 Months", "contact": "treasurer@stmaryscountymd.gov | (301) 475-4200"},
    "Talbot County": {"code": "TALB", "interest": "12.0% Annual", "redemption": "6 Months", "contact": "finance@talbotcountymd.gov | (410) 770-8020"},
}

# County portal targets for intelligent web crawling
COUNTY_PORTAL_TARGETS = [
    {
        "county": "Anne Arundel County",
        "portal_url": "https://www.aacounty.org/finance/tax-sale",
        "direct_urls": [
            ("Anne_Arundel_Remaining_Liens.pdf", "https://www.aacounty.org/sites/default/files/2026-06/remaining-liens-list.pdf"),
        ],
        "keywords": ["remaining", "over the counter", "otc", "unredeemed", "unsold", "lien"]
    },
    {
        "county": "Wicomico County",
        "portal_url": "https://www.wicomicocounty.org/392/Tax-Sale-Information",
        "direct_urls": [
            ("Wicomico_2026_OTC_Tax_Sale_List.pdf", "https://www.wicomicocounty.org/DocumentCenter/View/14387/2026-OVER-THE-COUNTER-LIST"),
        ],
        "keywords": ["over the counter", "over-the-counter", "otc", "remaining", "tax sale list"]
    },
    {
        "county": "Queen Anne's County",
        "portal_url": "https://www.qac.org/598/Tax-Sale",
        "direct_urls": [
            ("Queen_Annes_Available_OTC_Tax_Certs.pdf", "https://www.qac.org/DocumentCenter/View/26124"),
        ],
        "keywords": ["over the counter", "otc", "available", "certificate", "unredeemed"]
    },
    {
        "county": "Worcester County",
        "portal_url": "https://www.worcestermd.gov/departments/treasurer/sale",
        "direct_urls": [
            ("Worcester_2026_OTC_Tax_Liens.pdf", "https://www.worcestermd.gov/sites/default/files/2026-05/OverTheCounter.pdf"),
        ],
        "keywords": ["overthecounter", "over the counter", "otc", "remaining"]
    },
    {
        "county": "Cecil County",
        "portal_url": "https://www.cecilcountymd.gov/376/Tax-Sale",
        "direct_urls": [
            ("Cecil_County_Week_4_Tax_Sale_Advertisement.pdf", "https://www.cecilcountymd.gov/DocumentCenter/View/5971"),
        ],
        "keywords": ["over the counter", "otc", "tax sale", "advertisement", "unsold", "remaining"]
    },
    {
        "county": "Kent County",
        "portal_url": "https://www.kentcounty.com/finance",
        "direct_urls": [],
        "keywords": ["otc", "over the counter", "tax sale", "remaining"]
    },
    {
        "county": "Caroline County",
        "portal_url": "https://www.carolinemd.org/245/Tax-Sale",
        "direct_urls": [
            ("Caroline_County_2026_Tax_Sale_Results.pdf", "https://www.carolinecounty.org/DocumentCenter/View/12385/2026-TAX-SALE-RESULTS"),
        ],
        "keywords": ["over the counter", "otc", "tax sale", "remaining", "unsold"]
    },
    {
        "county": "Frederick County",
        "portal_url": "https://www.frederickcountymd.gov/2005/Tax-Sale",
        "direct_urls": [],
        "keywords": ["over the counter", "otc", "assignment", "remaining", "unsold"]
    },
    {
        "county": "Prince George's County",
        "portal_url": "https://taxsale.princegeorgescountymd.gov/",
        "direct_urls": [],
        "keywords": ["over the counter", "otc", "assignment", "remaining", "unsold"]
    },
]


def normalize_county_name(raw_name: str) -> str:
    if not raw_name:
        return "Anne Arundel County"
    cleaned = raw_name.strip()
    upper = cleaned.upper()
    for official in COUNTY_DEFAULTS.keys():
        off_upper = official.upper().replace(" COUNTY", "").replace("'", "")
        if off_upper in upper.replace("'", ""):
            return official
    return cleaned if "County" in cleaned or "City" in cleaned else f"{cleaned.title()} County"


def compute_tier(assessed: float, bid: float, ltv: float) -> str:
    if assessed <= 0 or ltv > 70.0:
        return "Tier 4: High Risk / Toxic"
    if ltv <= 25.0 or bid < 1500:
        return "Tier 1: Alpha / Micro-Lien"
    if assessed >= 50000 and ltv <= 50.0:
        return "Tier 2: High Equity ($50k+)"
    return "Tier 3: Infill / Cluster"


def parse_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = re.sub(r'[^0-9\.-]', '', str(val))
    try:
        return float(s) if s else default
    except ValueError:
        return default


def load_master_liens() -> List[Dict[str, Any]]:
    if os.path.exists(MASTER_JSON_PATH):
        try:
            with open(MASTER_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading master JSON: {e}")
    return []


def load_graded_deals() -> Dict[str, Any]:
    if os.path.exists(GRADED_JSON_PATH):
        try:
            with open(GRADED_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading graded JSON: {e}")
    return {"summary": {}, "grade_a": [], "grade_b": [], "grade_c": [], "grade_d": [], "grade_f": []}


def save_master_liens(records: List[Dict[str, Any]]) -> None:
    # Sort by LTV ascending
    records_sorted = sorted(records, key=lambda x: (float(x.get("ltv_pct", 999.0)), -float(x.get("assessed_value", 0))))
    with open(MASTER_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records_sorted, f, indent=2)

    # Also write updated CSV
    headers = [
        "County", "List / Item #", "Account / APN ID", "Owner of Record", "Property Address / Legal Description",
        "Assessed Value ($)", "Opening Bid / Lien ($)", "LTV (%)", "Equity Spread ($)",
        "Statutory Interest", "Redemption Window", "Investment Tier", "County Contact / Purchase Office"
    ]
    try:
        with open(CSV_OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records_sorted:
                writer.writerow([
                    r.get("county", ""),
                    r.get("list_no", ""),
                    r.get("account_id", ""),
                    r.get("owner", ""),
                    r.get("address", ""),
                    r.get("assessed_value", 0),
                    r.get("opening_bid", 0),
                    r.get("ltv_pct", 0),
                    r.get("equity_spread", 0),
                    r.get("statutory_interest", "12.0% Annual"),
                    r.get("redemption_window", "6 Months"),
                    r.get("tier", ""),
                    r.get("contact_info", "")
                ])
    except Exception as e:
        print(f"Notice writing CSV: {e}")


def detect_county_from_filename_or_text(filename: str, text_sample: str = "") -> str:
    combined = f"{filename} {text_sample[:1000]}".upper()
    if "ANNE ARUNDEL" in combined or "AACOUNTY" in combined or "ANNE-ARUNDELL" in combined:
        return "Anne Arundel County"
    if "KENT" in combined:
        return "Kent County"
    if "WICOMICO" in combined:
        return "Wicomico County"
    if "WORCESTER" in combined:
        return "Worcester County"
    if "QUEEN ANNE" in combined or "QAC" in combined:
        return "Queen Anne's County"
    if "CECIL" in combined:
        return "Cecil County"
    if "BALTIMORE CITY" in combined:
        return "Baltimore City"
    if "BALTIMORE COUNTY" in combined or "BALTIMORE_COUNTY" in combined:
        return "Baltimore County"
    if "PRINCE GEORGE" in combined:
        return "Prince George's County"
    if "CARROLL" in combined:
        return "Carroll County"
    if "FREDERICK" in combined:
        return "Frederick County"
    if "HOWARD" in combined:
        return "Howard County"
    if "CAROLINE" in combined:
        return "Caroline County"
    if "CHARLES" in combined:
        return "Charles County"
    return "Anne Arundel County"


def standardize_record(raw: Dict[str, Any], default_county: str = "Anne Arundel County") -> Optional[Dict[str, Any]]:
    county = normalize_county_name(raw.get("county") or default_county)
    c_meta = COUNTY_DEFAULTS.get(county, COUNTY_DEFAULTS["Anne Arundel County"])

    acct = str(
        raw.get("account_id")
        or raw.get("account_no")
        or raw.get("Account / APN ID")
        or raw.get("Account")
        or raw.get("Parcel")
        or raw.get("APN")
        or raw.get("Tax ID")
        or ""
    ).strip()

    if not acct or acct.lower() in ["none", "nan", "account", "parcel"]:
        return None

    owner = str(
        raw.get("owner")
        or raw.get("Owner of Record")
        or raw.get("Owner Name")
        or raw.get("Owner")
        or f"{county} Delinquent Owner"
    ).strip()

    address = str(
        raw.get("address")
        or raw.get("Property Address / Legal Description")
        or raw.get("Address")
        or raw.get("Property Description")
        or raw.get("Legal Description")
        or raw.get("Location")
        or ""
    ).strip()

    assessed = parse_float(
        raw.get("assessed_value")
        or raw.get("assessment")
        or raw.get("Assessed Value ($)")
        or raw.get("Assessed Value")
        or raw.get("Assessment")
        or 0.0
    )

    bid = parse_float(
        raw.get("opening_bid")
        or raw.get("total_due")
        or raw.get("bid_amount")
        or raw.get("Opening Bid / Lien ($)")
        or raw.get("Opening Bid")
        or raw.get("Total Due")
        or raw.get("Balance Due")
        or raw.get("Lien Amount")
        or 0.0
    )

    if bid <= 0 and assessed <= 0:
        return None

    list_no = str(
        raw.get("list_no")
        or raw.get("List / Item #")
        or raw.get("List #")
        or raw.get("Item #")
        or f"OTC-{c_meta['code']}-{acct}"
    ).strip()

    ltv = round((bid / assessed) * 100.0, 2) if assessed > 0 else 999.0
    spread = round(assessed - bid, 2)
    tier = raw.get("tier") or raw.get("Investment Tier") or compute_tier(assessed, bid, ltv)

    return {
        "county": county,
        "jurisdiction_code": raw.get("jurisdiction_code") or c_meta["code"],
        "list_no": list_no,
        "account_id": acct,
        "owner": owner,
        "address": address,
        "assessed_value": assessed,
        "opening_bid": bid,
        "ltv_pct": ltv,
        "equity_spread": spread,
        "statutory_interest": raw.get("statutory_interest") or c_meta["interest"],
        "redemption_window": raw.get("redemption_window") or c_meta["redemption"],
        "tier": tier,
        "contact_info": raw.get("contact_info") or c_meta["contact"],
        "imported_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def parse_pdf_otc_records(file_path: str, county_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    if not pypdf:
        return []
    records = []
    try:
        reader = pypdf.PdfReader(file_path)
        full_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        print(f"PDF read error on {file_path}: {e}")
        return []

    county = normalize_county_name(county_hint) if county_hint else detect_county_from_filename_or_text(os.path.basename(file_path), full_text)
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    # 1. Anne Arundel multi-line format: LIST# (1-4 digits) ACCOUNT# (12 digits)
    i = 0
    while i < len(lines):
        m_aa = re.match(r'^(\d{1,4})\s+(\d{12})$', lines[i])
        if m_aa and i + 7 < len(lines):
            list_no, acct = m_aa.groups()
            owner = lines[i + 1]
            assessed = parse_float(lines[i + 2])
            bid = parse_float(lines[i + 3])
            total_due = parse_float(lines[i + 7]) or bid
            rec = standardize_record({
                "county": "Anne Arundel County",
                "list_no": list_no,
                "account_id": acct,
                "owner": owner,
                "assessed_value": assessed,
                "opening_bid": total_due
            }, "Anne Arundel County")
            if rec:
                records.append(rec)
                i += 8
                continue
        i += 1

    if records:
        return records

    # 2. Line-by-line regex patterns for Kent, Wicomico, Worcester, Queen Anne's, Cecil, and general county tables
    for line in lines:
        # Anne Arundel single-line format: 58 188090034122 O'CONNOR DONALD J 28,700 424.26 424.26 0.00 31.82 456.08
        m_aa_single = re.match(
            r'^(\d{1,4})\s+(\d{12})\s+(.+?)\s+([\d,]+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$',
            line
        )
        if m_aa_single:
            list_no, acct, owner, assessed_s, bid_s, _, _, _, total_due_s = m_aa_single.groups()
            rec = standardize_record({
                "county": "Anne Arundel County",
                "list_no": list_no,
                "account_id": acct,
                "owner": owner,
                "assessed_value": assessed_s,
                "opening_bid": total_due_s or bid_s
            }, "Anne Arundel County")
            if rec:
                records.append(rec)
            continue

        # Prince George's County Assignment List format: 02 0183483 C & U INVESTMENT L 6011 EMERSON ST ... $85,333 $80,554.86
        m_pg = re.match(r'^(\d{2})\s+(\d{7})\s+(.+?)\s+\$([\d,]+)\s+\$([\d,]+\.\d{2})$', line)
        if m_pg:
            dist, acct7, middle, assessed_s, bid_s = m_pg.groups()
            full_acct = f"{dist}{acct7}"
            rec = standardize_record({
                "county": "Prince George's County",
                "list_no": f"PG-OTC-{full_acct}",
                "account_id": full_acct,
                "owner": middle[:32].strip(),
                "address": middle.strip(),
                "assessed_value": assessed_s,
                "opening_bid": bid_s
            }, "Prince George's County")
            if rec:
                records.append(rec)
            continue

        # Kent format: 06008011 LOMAX GEORGE B & SHELIA E 19,600 666.92$ LOT 2 AC...
        m_kent = re.match(r'^(\d{8})\s+(.+?)\s+([\d,]+)\s+([\d,]+\.\d{2})\$\s+(.+)$', line)
        if m_kent:
            acct, owner, assessed_s, bid_s, legal = m_kent.groups()
            rec = standardize_record({
                "county": county or "Kent County",
                "list_no": f"OTC-KENT-{acct}",
                "account_id": acct,
                "owner": owner,
                "address": legal,
                "assessed_value": assessed_s,
                "opening_bid": bid_s
            }, county)
            if rec:
                records.append(rec)
            continue

        # Wicomico format: 5 05003431 OWNER NAME 10800 DESCRIPTION 153615.5
        m_wico = re.match(r'^(\d+)\s+(\d{8})\s+(.+?)\s+(\d+)\s+(.+?)\s+([\d,]+\.\d+)$', line)
        if m_wico:
            list_no, acct, owner, assessed_s, desc, bid_s = m_wico.groups()
            rec = standardize_record({
                "county": county or "Wicomico County",
                "list_no": list_no,
                "account_id": acct,
                "owner": owner,
                "address": desc,
                "assessed_value": assessed_s,
                "opening_bid": bid_s
            }, county)
            if rec:
                records.append(rec)
            continue

        # Worcester format: 36 01012444 Colona Rd ... 1,281.01$ Knox, Levi Rubben 19,300
        m_worc = re.match(r'^(\d+)\s+(\d{8})\s+(.+?)\s+([\d,]+\.\d{2})\$\s+(.+?)\s+([\d,]+)', line)
        if m_worc:
            list_no, acct, desc, bid_s, owner, assessed_s = m_worc.groups()
            rec = standardize_record({
                "county": county or "Worcester County",
                "list_no": list_no,
                "account_id": acct,
                "owner": owner,
                "address": desc,
                "assessed_value": assessed_s,
                "opening_bid": bid_s
            }, county)
            if rec:
                records.append(rec)
            continue

        # Cecil format: 03-095894 LOT 8... $18,800 $791.48
        m_cecil = re.match(r'^(\d{2}-\d{6})\s+(.+?)\s+\$([\d,]+)\s+\$([\d,]+\.\d{2})', line)
        if m_cecil:
            acct, desc, assessed_s, bid_s = m_cecil.groups()
            rec = standardize_record({
                "county": county or "Cecil County",
                "list_no": f"CECI-{acct}",
                "account_id": acct,
                "owner": f"{county} Delinquent",
                "address": desc[:80],
                "assessed_value": assessed_s,
                "opening_bid": bid_s
            }, county)
            if rec:
                records.append(rec)
            continue

        # Queen Anne's format: 2025 02-027208 0 REEAND LN
        m_qa = re.match(r'^(202\d)\s+(\d{2}-\d{6})\s+(.+)$', line)
        if m_qa:
            yr, acct, addr = m_qa.groups()
            rec = standardize_record({
                "county": county or "Queen Anne's County",
                "list_no": f"QA-OTC-{yr}",
                "account_id": acct,
                "owner": "Queen Anne's County Held",
                "address": addr,
                "assessed_value": 45000.0,
                "opening_bid": 2500.0
            }, county)
            if rec:
                records.append(rec)
            continue

        # Generic fallback: Account ID (8-15 digits or XX-XXXXXX) + text + 1 or 2 dollar values
        m_gen = re.match(r'^(?:(\d{1,4})\s+)?([0-9]{2}-[0-9]{6,8}|[0-9]{8,15})\s+(.+?)\s+\$?([\d,]+(?:\.\d{2})?)\s+\$?([\d,]+\.\d{2})$', line)
        if m_gen:
            list_no, acct, middle, val1, val2 = m_gen.groups()
            v1 = parse_float(val1)
            v2 = parse_float(val2)
            assessed = max(v1, v2)
            bid = min(v1, v2)
            rec = standardize_record({
                "county": county,
                "list_no": list_no or f"OTC-{acct}",
                "account_id": acct,
                "owner": middle[:45].strip(),
                "address": middle.strip(),
                "assessed_value": assessed,
                "opening_bid": bid
            }, county)
            if rec:
                records.append(rec)

    return records


def parse_csv_otc_records(file_path: str, county_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    records = []
    default_county = normalize_county_name(county_hint) if county_hint else detect_county_from_filename_or_text(os.path.basename(file_path))
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = standardize_record(row, default_county)
            if rec:
                records.append(rec)
    return records


def parse_excel_otc_records(file_path: str, county_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    if not openpyxl:
        return []
    records = []
    default_county = normalize_county_name(county_hint) if county_hint else detect_county_from_filename_or_text(os.path.basename(file_path))
    wb = openpyxl.load_workbook(file_path, data_only=True)
    for sheet_name in wb.sheetnames:
        if "directory" in sheet_name.lower():
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            continue
        # Find header row
        header_idx = 0
        for idx, r in enumerate(rows[:5]):
            row_str = " ".join(str(c or "") for c in r).lower()
            if any(k in row_str for k in ["account", "parcel", "apn", "owner", "assessed", "bid", "lien"]):
                header_idx = idx
                break
        headers = [str(h or f"col_{i}").strip() for i, h in enumerate(rows[header_idx])]
        for r in rows[header_idx + 1:]:
            row_dict = {headers[i]: r[i] for i in range(min(len(headers), len(r)))}
            rec = standardize_record(row_dict, default_county)
            if rec:
                records.append(rec)
    return records


def enrich_and_grade_subset(new_records: List[Dict[str, Any]], max_sdat_lookups: int = 25) -> Dict[str, int]:
    """
    Runs SDAT cadastre & Title Confluence Engine on newly imported low-LTV candidate deals
    and merges Grade A / Grade B deals into scratch/otc_graded_deals.json.
    """
    graded_data = load_graded_deals()
    existing_accts = set()
    for g_key in ["grade_a", "grade_b", "grade_c", "grade_d", "grade_f"]:
        for item in graded_data.get(g_key, []):
            existing_accts.add(str(item.get("account_no", "")).strip())

    # Prioritize low-LTV / high-equity new records that aren't graded yet
    candidates = [
        r for r in new_records
        if str(r.get("account_id", "")).strip() not in existing_accts
    ]
    candidates.sort(key=lambda x: (x.get("ltv_pct", 999.0), -x.get("assessed_value", 0)))

    added_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for r in candidates[:max_sdat_lookups]:
        acct = str(r.get("account_id", "")).strip()
        county_name = r.get("county", "Anne Arundel County").replace(" County", "")
        props = search_maryland_property(acct, county=county_name)
        if not props and r.get("address"):
            props = search_maryland_property(r["address"], county=county_name)
        if not props:
            continue

        prop = props[0]
        tot_assmt = float(prop.get("valuation", {}).get("total_value") or r.get("assessed_value") or 0)
        tax_lien = float(r.get("opening_bid") or 0)
        if tot_assmt > 0:
            r["assessed_value"] = tot_assmt
            r["ltv_pct"] = round((tax_lien / tot_assmt) * 100.0, 2)
            r["equity_spread"] = round(tot_assmt - tax_lien, 2)
            r["tier"] = compute_tier(tot_assmt, tax_lien, r["ltv_pct"])
        if prop.get("address") and not r.get("address"):
            r["address"] = f"{prop.get('address')}, {prop.get('city', '')}".strip(", ")

        tax_info = {
            "tax_lien_amount": tax_lien,
            "assessed_value": tot_assmt,
            "owner_of_record": r.get("owner"),
            "tax_sale_flag": False
        }
        title_res = analyze_maryland_title(prop, tax_info)
        grade_letter = title_res["grade"]

        dims = prop.get("dimensions", {})
        acres = dims.get("acres")
        sqft = dims.get("sqft")

        graded_entry = {
            "list_no": r.get("list_no"),
            "account_no": acct,
            "acct_id_imap": prop.get("account_id", acct),
            "county": r.get("county"),
            "address": prop.get("address") or r.get("address"),
            "city": prop.get("city", ""),
            "zipcode": prop.get("zipcode", ""),
            "owner": r.get("owner") or prop.get("owner_mailing", {}).get("line1", ""),
            "land_value": prop.get("valuation", {}).get("land_value") or 0,
            "structure_value": prop.get("valuation", {}).get("improvement_value") or 0,
            "total_assessed": tot_assmt,
            "tax_lien_amount": tax_lien,
            "ltv_pct": r["ltv_pct"],
            "zoning": prop.get("zoning", {}).get("code"),
            "land_area": f"{acres} Acres" if acres else (f"{sqft} Sq Ft" if sqft else "N/A"),
            "title_score": title_res["score"],
            "grade": grade_letter,
            "grade_desc": title_res["grade_desc"],
            "badge": title_res["badge"],
            "entity_type": title_res["entity_type"],
            "current_deed": title_res["current_deed"],
            "prior_deed": title_res["prior_deed"],
            "plat": title_res["plat"],
            "positive_factors": title_res["positive_factors"],
            "risk_factors": title_res["risk_factors"],
            "recommended_contingencies": title_res["recommended_contingencies"],
            "google_maps_url": prop.get("google_maps_url") or "",
            "sdat_url": prop.get("sdat_web_url") or "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
        }

        target_key = f"grade_{grade_letter.lower()}"
        if target_key not in graded_data:
            graded_data[target_key] = []
        graded_data[target_key].append(graded_entry)
        added_counts[grade_letter] = added_counts.get(grade_letter, 0) + 1

    if sum(added_counts.values()) > 0:
        for k in ["grade_a", "grade_b", "grade_c", "grade_d", "grade_f"]:
            graded_data[k] = sorted(
                graded_data.get(k, []),
                key=lambda x: (-float(x.get("total_assessed", 0)), float(x.get("ltv_pct", 999.0)))
            )
        graded_data["summary"] = {
            "total_screened": sum(len(graded_data.get(k, [])) for k in ["grade_a", "grade_b", "grade_c", "grade_d", "grade_f"]),
            "grade_a_count": len(graded_data.get("grade_a", [])),
            "grade_b_count": len(graded_data.get("grade_b", [])),
            "grade_c_count": len(graded_data.get("grade_c", [])),
            "grade_d_count": len(graded_data.get("grade_d", [])),
            "grade_f_count": len(graded_data.get("grade_f", [])),
        }
        with open(GRADED_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(graded_data, f, indent=2)

    return added_counts


def import_otc_file(file_path: str, county_hint: Optional[str] = None, enrich_sdat: bool = True) -> Dict[str, Any]:
    """
    Universal OTC file importer for CSV, XLSX, PDF, and JSON files.
    Merges and deduplicates against the master database and hot-reloads the index.
    """
    ext = os.path.splitext(file_path)[1].lower()
    parsed_records: List[Dict[str, Any]] = []

    if ext == ".csv":
        parsed_records = parse_csv_otc_records(file_path, county_hint)
    elif ext in [".xlsx", ".xls"]:
        parsed_records = parse_excel_otc_records(file_path, county_hint)
    elif ext == ".pdf":
        parsed_records = parse_pdf_otc_records(file_path, county_hint)
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            items = raw_data if isinstance(raw_data, list) else raw_data.get("records", [])
            for item in items:
                rec = standardize_record(item, county_hint or "Anne Arundel County")
                if rec:
                    parsed_records.append(rec)

    if not parsed_records:
        return {
            "status": "error",
            "message": f"No valid OTC tax lien records could be parsed from {os.path.basename(file_path)}.",
            "parsed_count": 0,
            "new_count": 0,
            "updated_count": 0
        }

    master_records = load_master_liens()
    index_by_key: Dict[str, int] = {}
    for idx, r in enumerate(master_records):
        key = f"{r.get('county', '')}::{re.sub(r'\\D', '', str(r.get('account_id', '')))}"
        index_by_key[key] = idx

    new_count = 0
    updated_count = 0
    newly_added_list = []

    for rec in parsed_records:
        clean_acct = re.sub(r'\D', '', str(rec.get("account_id", "")))
        key = f"{rec.get('county', '')}::{clean_acct}"
        if key in index_by_key:
            existing_idx = index_by_key[key]
            master_records[existing_idx].update(rec)
            updated_count += 1
        else:
            index_by_key[key] = len(master_records)
            master_records.append(rec)
            newly_added_list.append(rec)
            new_count += 1

    graded_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    if enrich_sdat and newly_added_list:
        graded_counts = enrich_and_grade_subset(newly_added_list, max_sdat_lookups=20)

    save_master_liens(master_records)

    # Hot-reload tax_lien_checker in memory
    try:
        from tax_lien_checker import reload_otc_databases
        reload_otc_databases()
    except Exception:
        pass

    # Refresh Obsidian mindmaps & Canvas
    try:
        from mindmap_sync import refresh_all_mindmaps
        refresh_all_mindmaps()
    except Exception:
        pass

    # Log to log.md
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counties_in_batch = sorted(list(set(r["county"] for r in parsed_records)))
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(
                    f"\n- **{now_str}** | `INGESTION`: Imported OTC file `{os.path.basename(file_path)}` "
                    f"({len(parsed_records)} parsed, {new_count} new, {updated_count} updated) across {', '.join(counties_in_batch)}."
                )
    except Exception:
        pass

    tier1_picks = [r for r in parsed_records if "Tier 1" in str(r.get("tier", ""))]
    tier1_picks.sort(key=lambda x: x.get("ltv_pct", 999.0))

    return {
        "status": "success",
        "file": os.path.basename(file_path),
        "counties": counties_in_batch,
        "parsed_count": len(parsed_records),
        "new_count": new_count,
        "updated_count": updated_count,
        "total_master_count": len(master_records),
        "graded_additions": graded_counts,
        "top_picks": tier1_picks[:5]
    }


def _get_http_session():
    if cffi_requests:
        return cffi_requests.Session(impersonate="chrome124")
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"})
    return s


def sync_all_county_websites() -> Dict[str, Any]:
    """
    Intelligently crawls official Maryland county tax sale websites & DocumentCenters,
    discovers OTC / Remaining Lien PDF, Excel, and CSV links, downloads updates,
    and imports them into the live master database.
    """
    session = _get_http_session()
    discovered_files = []
    import_summaries = []
    errors = []

    for target in COUNTY_PORTAL_TARGETS:
        county = target["county"]
        portal_url = target["portal_url"]
        candidate_links: List[Tuple[str, str]] = list(target.get("direct_urls", []))

        # Scrape county portal page for dynamic OTC / Remaining Lien links
        try:
            resp = session.get(portal_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    link_text = (a.get_text() or "").strip().lower()
                    combined = f"{href.lower()} {link_text}"

                    is_doc = any(ext in href.lower() for ext in [".pdf", ".xlsx", ".xls", ".csv", "documentcenter/view"])
                    matches_kw = any(kw in combined for kw in target.get("keywords", []))
                    is_excess_only = any(ex in combined for ex in ["excess", "surplus", "bidder contract", "w-9", "w9"])

                    if is_doc and matches_kw and not is_excess_only:
                        full_url = urllib.parse.urljoin(portal_url, href)
                        safe_name = re.sub(r'[^A-Za-z0-9_\.-]', '_', os.path.basename(urllib.parse.urlparse(full_url).path))
                        if not any(safe_name.lower().endswith(e) for e in [".pdf", ".xlsx", ".xls", ".csv"]):
                            safe_name = f"{county.replace(' ', '_')}_{safe_name}.pdf"
                        if full_url not in [u for _, u in candidate_links]:
                            candidate_links.append((safe_name, full_url))
        except Exception as e:
            errors.append(f"{county} portal check notice: {str(e)[:80]}")

        # Download and import each discovered link
        for filename, url in candidate_links:
            out_path = os.path.join(AUTO_SYNC_DIR, filename)
            try:
                r_doc = session.get(url, timeout=25)
                if r_doc.status_code == 200 and len(r_doc.content) > 500:
                    content_type = (r_doc.headers.get("Content-Type") or "").lower()
                    if "html" in content_type and not r_doc.content[:4].startswith(b"%PDF"):
                        continue

                    with open(out_path, "wb") as f:
                        f.write(r_doc.content)

                    discovered_files.append({"county": county, "file": filename, "url": url, "bytes": len(r_doc.content)})
                    imp_res = import_otc_file(out_path, county_hint=county, enrich_sdat=False)
                    if imp_res.get("parsed_count", 0) > 0:
                        import_summaries.append(imp_res)
            except Exception as e:
                errors.append(f"{county} ({filename}): {str(e)[:80]}")

    # Also ensure any local raw files in raw/ are indexed
    local_Sync_files = [
        ("Anne Arundel County", os.path.join(RAW_DIR, "Anne-Arundell-list-of-liens.pdf")),
        ("Kent County", os.path.join(RAW_DIR, "Kent County 2026 Tax Sale - OTC 6.9.26.pdf")),
        ("Wicomico County", os.path.join(RAW_DIR, "Wicomico_County_Over_the_Counter_List.pdf")),
        ("Worcester County", os.path.join(RAW_DIR, "Worcester_County_Over_the_Counter_Lien_from_Tax.pdf")),
        ("Queen Anne's County", os.path.join(RAW_DIR, "Queen_Anne_s_County_Available_Over_the_Counter_Tax.pdf")),
        ("Cecil County", os.path.join(RAW_DIR, "Cecil_County_Week_4_Tax_Sale_Advertisement.pdf")),
    ]
    for c_name, f_path in local_Sync_files:
        if os.path.exists(f_path):
            imp_res = import_otc_file(f_path, county_hint=c_name, enrich_sdat=False)
            if imp_res.get("new_count", 0) > 0:
                import_summaries.append(imp_res)

    master_records = load_master_liens()
    total_new = sum(s.get("new_count", 0) for s in import_summaries)
    total_updated = sum(s.get("updated_count", 0) for s in import_summaries)

    sync_report = {
        "last_sync": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "portals_checked": len(COUNTY_PORTAL_TARGETS),
        "files_downloaded": len(discovered_files),
        "new_liens_added": total_new,
        "liens_updated": total_updated,
        "total_master_liens": len(master_records),
        "counties_active": sorted(list(set(r.get("county", "") for r in master_records))),
        "discovered_files": discovered_files,
        "notices": errors[:5]
    }

    with open(SYNC_STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(sync_report, f, indent=2)

    try:
        from mindmap_sync import refresh_all_mindmaps
        refresh_all_mindmaps()
    except Exception:
        pass

    return sync_report


if __name__ == "__main__":
    print("Running Maryland County OTC Auto-Sync...")
    report = sync_all_county_websites()
    print(json.dumps(report, indent=2))
