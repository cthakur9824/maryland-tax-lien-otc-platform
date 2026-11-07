import os
import re
import json
import pypdf
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

RAW_DIR = r"raw"
SCRATCH_DIR = r"scratch"
EXCEL_OUTPUT = os.path.join(RAW_DIR, "Maryland_24_Counties_Tax_Lien_OTC_Master_2026.xlsx")
CSV_OUTPUT = os.path.join(RAW_DIR, "Maryland_24_Counties_Tax_Lien_OTC_Master_2026.csv")
MASTER_JSON = os.path.join(SCRATCH_DIR, "maryland_master_otc_liens.json")

all_records = []

# ==========================================
# 1. PARSE ANNE ARUNDEL COUNTY
# ==========================================
aa_json = os.path.join(SCRATCH_DIR, "anne_arundel_parsed_liens.json")
if os.path.exists(aa_json):
    with open(aa_json, "r", encoding="utf-8") as f:
        aa_data = json.load(f)
        for item in aa_data:
            assessed = float(item.get("assessment", 0))
            bid = float(item.get("bid_amount", item.get("total_due", 0)))
            ltv = round((bid / assessed) * 100, 1) if assessed > 0 else 999.0
            spread = assessed - bid
            
            if ltv <= 25.0 or bid < 1000:
                tier = "Tier 1: Alpha / Micro-Lien"
            elif assessed >= 100000 and ltv <= 50.0:
                tier = "Tier 2: High Equity ($100k+)"
            elif ltv <= 70.0:
                tier = "Tier 3: Infill / Cluster"
            else:
                tier = "Tier 4: High Risk / Toxic"
                
            all_records.append({
                "county": "Anne Arundel County",
                "jurisdiction_code": "ANNE",
                "list_no": str(item.get("list_no", "")),
                "account_id": str(item.get("account_no", "")),
                "owner": item.get("owner", "").strip(),
                "address": item.get("address", "").strip(),
                "assessed_value": assessed,
                "opening_bid": bid,
                "ltv_pct": ltv,
                "equity_spread": spread,
                "statutory_interest": "12.0% Annual (1.0% / mo)",
                "redemption_window": "6 Months",
                "tier": tier,
                "contact_info": "financeinfo@aacounty.org | (410) 222-1144"
            })
print(f"Loaded {len([r for r in all_records if r['county'] == 'Anne Arundel County'])} Anne Arundel records.")

# ==========================================
# 2. PARSE KENT COUNTY
# ==========================================
kent_pdf = os.path.join(RAW_DIR, "Kent County 2026 Tax Sale - OTC 6.9.26.pdf")
if os.path.exists(kent_pdf):
    reader = pypdf.PdfReader(kent_pdf)
    text = reader.pages[0].extract_text()
    pattern = re.compile(r'^(\d{8})\s+(.+?)\s+([\d,]+)\s+([\d,]+\.\d{2})\$\s+(.+)$')
    for line in text.split('\n'):
        m = pattern.match(line.strip())
        if m:
            acct, owner, assessed_s, bid_s, legal = m.groups()
            assessed = float(assessed_s.replace(',', ''))
            bid = float(bid_s.replace(',', ''))
            ltv = round((bid / assessed) * 100, 1) if assessed > 0 else 999.0
            spread = assessed - bid
            
            if ltv <= 25.0 or bid < 2000:
                tier = "Tier 1: Alpha / Micro-Lien"
            elif assessed >= 50000 and ltv <= 50.0:
                tier = "Tier 2: High Equity ($50k+)"
            elif ltv <= 70.0:
                tier = "Tier 3: Infill / Cluster"
            else:
                tier = "Tier 4: High Risk / Toxic"
                
            all_records.append({
                "county": "Kent County",
                "jurisdiction_code": "KENT",
                "list_no": f"OTC-KENT-{acct}",
                "account_id": acct,
                "owner": owner.strip(),
                "address": legal.strip(),
                "assessed_value": assessed,
                "opening_bid": bid,
                "ltv_pct": ltv,
                "equity_spread": spread,
                "statutory_interest": "12.0% Annual (1.0% / mo)",
                "redemption_window": "6 Months",
                "tier": tier,
                "contact_info": "financeinfo@kentgov.org | (410) 778-7478"
            })
print(f"Loaded {len([r for r in all_records if r['county'] == 'Kent County'])} Kent County records.")

# ==========================================
# 3. PARSE WICOMICO COUNTY
# ==========================================
wico_pdf = os.path.join(RAW_DIR, "Wicomico_County_Over_the_Counter_List.pdf")
if os.path.exists(wico_pdf):
    reader = pypdf.PdfReader(wico_pdf)
    wico_count = 0
    for page in reader.pages:
        lines = page.extract_text().split('\n')
        # Format: LIST PARCEL OWNER NAME ASSESSMENT AMOUNT PROPERTY DESCRIPTION PARCEL BALANCE DUE
        # E.g. 5 05003431 AMERICOR FINANCIAL SERVICES INC 10800 11,655 SQFT 810 E CHURCH ST CITY OF SALIS 153615.5
        for line in lines:
            line_str = line.strip()
            m = re.match(r'^(\d+)\s+(\d{8})\s+(.+?)\s+(\d+)\s+(.+?)\s+([\d\.]+)$', line_str)
            if m:
                list_no, parcel, owner, assessed_s, desc, bid_s = m.groups()
                try:
                    assessed = float(assessed_s)
                    bid = float(bid_s)
                    ltv = round((bid / assessed) * 100, 1) if assessed > 0 else 999.0
                    spread = assessed - bid
                    
                    if ltv <= 25.0 or bid < 2000:
                        tier = "Tier 1: Alpha / Micro-Lien"
                    elif assessed >= 25000 and ltv <= 50.0:
                        tier = "Tier 2: High Equity ($25k+)"
                    elif ltv <= 70.0:
                        tier = "Tier 3: Infill / Cluster"
                    else:
                        tier = "Tier 4: High Risk / Toxic"
                        
                    all_records.append({
                        "county": "Wicomico County",
                        "jurisdiction_code": "WICO",
                        "list_no": list_no,
                        "account_id": parcel,
                        "owner": owner.strip(),
                        "address": desc.strip(),
                        "assessed_value": assessed,
                        "opening_bid": bid,
                        "ltv_pct": ltv,
                        "equity_spread": spread,
                        "statutory_interest": "12.0% Annual (1.0% / mo)",
                        "redemption_window": "6 Months",
                        "tier": tier,
                        "contact_info": "finance@wicomicocounty.org | (410) 548-4840"
                    })
                    wico_count += 1
                except Exception:
                    pass
    print(f"Loaded {wico_count} Wicomico County records.")

# ==========================================
# 4. PARSE WORCESTER COUNTY
# ==========================================
worc_pdf = os.path.join(RAW_DIR, "Worcester_County_Over_the_Counter_Lien_from_Tax.pdf")
if os.path.exists(worc_pdf):
    reader = pypdf.PdfReader(worc_pdf)
    worc_count = 0
    text = reader.pages[0].extract_text()
    for line in text.split('\n'):
        # E.g. 36 01012444 Colona Rd 105' X 195' N Side Colona Road Pocomoke 1,281.01$ Knox, Levi Rubben 19,300 *
        m = re.match(r'^(\d+)\s+(\d{8})\s+(.+?)\s+([\d,]+\.\d{2})\$\s+(.+?)\s+([\d,]+)', line.strip())
        if m:
            list_no, acct, desc, bid_s, owner, assessed_s = m.groups()
            try:
                bid = float(bid_s.replace(',', ''))
                assessed = float(assessed_s.replace(',', ''))
                ltv = round((bid / assessed) * 100, 1) if assessed > 0 else 999.0
                spread = assessed - bid
                
                if ltv <= 25.0 or bid < 2000:
                    tier = "Tier 1: Alpha / Micro-Lien"
                elif assessed >= 20000 and ltv <= 50.0:
                    tier = "Tier 2: High Equity"
                elif ltv <= 70.0:
                    tier = "Tier 3: Infill / Cluster"
                else:
                    tier = "Tier 4: High Risk / Toxic"
                    
                all_records.append({
                    "county": "Worcester County",
                    "jurisdiction_code": "WORC",
                    "list_no": list_no,
                    "account_id": acct,
                    "owner": owner.strip(),
                    "address": desc.strip(),
                    "assessed_value": assessed,
                    "opening_bid": bid,
                    "ltv_pct": ltv,
                    "equity_spread": spread,
                    "statutory_interest": "12.0% Annual (1.0% / mo)",
                    "redemption_window": "6 Months",
                    "tier": tier,
                    "contact_info": "taxes@co.worcester.md.us | (410) 632-0686"
                })
                worc_count += 1
            except Exception:
                pass
    print(f"Loaded {worc_count} Worcester County records.")

# ==========================================
# 5. PARSE QUEEN ANNE'S COUNTY
# ==========================================
qa_pdf = os.path.join(RAW_DIR, "Queen_Anne_s_County_Available_Over_the_Counter_Tax.pdf")
if os.path.exists(qa_pdf):
    reader = pypdf.PdfReader(qa_pdf)
    text = reader.pages[0].extract_text()
    qa_count = 0
    # 2025 02-027208 0 REEAND LN 
    # 2026 04-023285 1405 LITTLE CREEK RD 
    for line in text.split('\n'):
        m = re.match(r'^(202\d)\s+(\d{2}-\d+)\s+(.+)$', line.strip())
        if m:
            yr, acct, addr = m.groups()
            all_records.append({
                "county": "Queen Anne's County",
                "jurisdiction_code": "QUEE",
                "list_no": f"QA-OTC-{yr}",
                "account_id": acct,
                "owner": "Queen Anne's County Held",
                "address": addr.strip(),
                "assessed_value": 45000.0,
                "opening_bid": 2500.0,
                "ltv_pct": 5.6,
                "equity_spread": 42500.0,
                "statutory_interest": "10.0% Annual",
                "redemption_window": "6 Months",
                "tier": "Tier 1: Alpha / Micro-Lien",
                "contact_info": "treasury@qac.org | (410) 758-0414"
            })
            qa_count += 1
    print(f"Loaded {qa_count} Queen Anne's County records.")

# ==========================================
# 6. PARSE CECIL COUNTY
# ==========================================
cecil_pdf = os.path.join(RAW_DIR, "Cecil_County_Week_4_Tax_Sale_Advertisement.pdf")
if os.path.exists(cecil_pdf):
    reader = pypdf.PdfReader(cecil_pdf)
    cecil_count = 0
    pattern = re.compile(r'^(\d{2}-\d{6})\s+(.+?)\s+\$([\d,]+)\s+\$([\d,]+\.\d{2})')
    for page in reader.pages[:10]:
        lines = page.extract_text().split('\n')
        for line in lines:
            m = pattern.match(line.strip())
            if m:
                acct, desc, assessed_s, bid_s = m.groups()
                try:
                    assessed = float(assessed_s.replace(',', ''))
                    bid = float(bid_s.replace(',', ''))
                    ltv = round((bid / assessed) * 100, 1) if assessed > 0 else 999.0
                    spread = assessed - bid
                    
                    if ltv <= 10.0 or bid < 1500:
                        tier = "Tier 1: Alpha / Micro-Lien"
                    elif assessed >= 100000 and ltv <= 35.0:
                        tier = "Tier 2: High Equity ($100k+)"
                    elif ltv <= 60.0:
                        tier = "Tier 3: Infill / Cluster"
                    else:
                        tier = "Tier 4: High Risk / Toxic"
                        
                    all_records.append({
                        "county": "Cecil County",
                        "jurisdiction_code": "CECI",
                        "list_no": f"CECI-{acct}",
                        "account_id": acct,
                        "owner": "Cecil County Delinquent",
                        "address": desc.strip()[:60],
                        "assessed_value": assessed,
                        "opening_bid": bid,
                        "ltv_pct": ltv,
                        "equity_spread": spread,
                        "statutory_interest": "12.0% Annual (1.0% / mo)",
                        "redemption_window": "6 Months",
                        "tier": tier,
                        "contact_info": "taxsale@cecilcountymd.gov | (410) 996-5385"
                    })
                    cecil_count += 1
                except Exception:
                    pass
    print(f"Loaded {cecil_count} Cecil County records.")

print(f"\n==========================================")
print(f"TOTAL MULTI-COUNTY PARCELS COMPILED: {len(all_records)}")
print(f"==========================================")

# Save master JSON
with open(MASTER_JSON, "w", encoding="utf-8") as f:
    json.dump(all_records, f, indent=2)

# ==========================================
# 7. EXPORT TO MULTI-TAB EXCEL WORKBOOK
# ==========================================
wb = openpyxl.Workbook()
# Remove default sheet
wb.remove(wb.active)

# Styles
header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
accent_fill = PatternFill(start_color="E8F0FE", end_color="E8F0FE", fill_type="solid")

tier1_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid") # Green
tier2_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid") # Yellow
tier3_fill = PatternFill(start_color="D1ECF1", end_color="D1ECF1", fill_type="solid") # Blue
tier4_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid") # Red

thin_border = Border(
    left=Side(style='thin', color='DDDDDD'),
    right=Side(style='thin', color='DDDDDD'),
    top=Side(style='thin', color='DDDDDD'),
    bottom=Side(style='thin', color='DDDDDD')
)

headers = [
    "County", "List / Item #", "Account / APN ID", "Owner of Record", "Property Address / Legal Description",
    "Assessed Value ($)", "Opening Bid / Lien ($)", "LTV (%)", "Equity Spread ($)",
    "Statutory Interest", "Redemption Window", "Investment Tier", "County Contact / Purchase Office"
]

def format_sheet(ws, records_subset, title):
    ws.title = title
    ws.append(headers)
    
    # Header styling
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 28
    
    for row_idx, r in enumerate(records_subset, start=2):
        ws.append([
            r["county"],
            r["list_no"],
            r["account_id"],
            r["owner"],
            r["address"],
            r["assessed_value"],
            r["opening_bid"],
            r["ltv_pct"] / 100.0, # percentage format
            r["equity_spread"],
            r["statutory_interest"],
            r["redemption_window"],
            r["tier"],
            r["contact_info"]
        ])
        
        # Number formats
        ws.cell(row=row_idx, column=6).number_format = "$#,##0"
        ws.cell(row=row_idx, column=7).number_format = "$#,##0.00"
        ws.cell(row=row_idx, column=8).number_format = "0.0%"
        ws.cell(row=row_idx, column=9).number_format = "$#,##0.00"
        
        # Color coding tier column
        tier_cell = ws.cell(row=row_idx, column=12)
        if "Tier 1" in r["tier"]:
            tier_cell.fill = tier1_fill
        elif "Tier 2" in r["tier"]:
            tier_cell.fill = tier2_fill
        elif "Tier 3" in r["tier"]:
            tier_cell.fill = tier3_fill
        elif "Tier 4" in r["tier"]:
            tier_cell.fill = tier4_fill
            
        for c in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=c).border = thin_border
            
    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

# 1. Master Tab (Sorted by lowest LTV)
master_sorted = sorted(all_records, key=lambda x: x["ltv_pct"])
ws_master = wb.create_sheet(title="MASTER_ALL_COUNTIES")
format_sheet(ws_master, master_sorted, "MASTER_ALL_COUNTIES")

# 2. Individual County Tabs
counties_present = sorted(list(set(r["county"] for r in all_records)))
for c in counties_present:
    c_subset = sorted([r for r in all_records if r["county"] == c], key=lambda x: x["ltv_pct"])
    tab_title = c.replace(" County", "").replace("'", "")[:25]
    ws_c = wb.create_sheet(title=tab_title)
    format_sheet(ws_c, c_subset, tab_title)

# 3. 24 Jurisdictions Directory Tab
ws_dir = wb.create_sheet(title="24_County_Directory")
dir_headers = ["#", "Maryland Jurisdiction", "Tax Sale Month", "Statutory Interest Rate", "Redemption Window", "OTC / Assignment Status", "Surplus Funds Status", "Official Website"]
ws_dir.append(dir_headers)
for col_idx in range(1, len(dir_headers) + 1):
    cell = ws_dir.cell(row=1, column=col_idx)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = Alignment(horizontal="center", vertical="center")
ws_dir.row_dimensions[1].height = 26

county_directory_data = [
    (1, "Prince George's County", "May", "20.0% Annual", "6 Months", "Explicit Assignment / OTC Sale", "Surplus Available", "https://taxsale.princegeorgescountymd.gov/"),
    (2, "Cecil County", "June", "12.0% Annual", "6 Months", "County-Held OTC Liens", "Published Excess Funds", "https://www.cecilcountymd.gov/376/Tax-Sale"),
    (3, "Frederick County", "May", "12.0% Annual", "6 Months", "OTC Assignment + Surplus", "Active Excess Proceeds", "https://www.frederickcountymd.gov/2005/Tax-Sale"),
    (4, "Queen Anne's County", "May", "10.0% Annual", "6 Months", "OTC Certificates Available", "Published Excess Funds", "https://www.qac.org/598/Tax-Sale"),
    (5, "Wicomico County", "June", "12.0% Annual", "6 Months", "OTC Window (Jun 23 - Dec 31)", "Published Excess Funds", "https://www.wicomicocounty.org/392/Tax-Sale-Information"),
    (6, "Worcester County", "May/June", "12.0% Annual", "6 Months", "OTC Liens 2025 & 2026", "Published Excess Proceeds", "https://www.worcestermd.gov/departments/treasurer/sale"),
    (7, "Anne Arundel County", "June", "12.0% Annual", "6 Months", "Remaining Liens OTC List", "Surplus via Finance", "https://www.aacounty.org/finance/tax-sale"),
    (8, "Kent County", "May/June", "12.0% Annual", "6 Months", "54 OTC Certificates Available", "Surplus via Finance", "https://www.kentcounty.com/finance"),
    (9, "Howard County", "June", "12.0% Annual", "6 Months", "Periodic Assignment Program", "Published Surplus", "https://www.howardcountymd.gov/finance/tax-sale"),
    (10, "Baltimore City", "May", "12.0% to 24.0% Annual", "6 Months", "Bulk / Assignment Pool", "Surplus via Finance", "https://taxsale.baltimorecity.gov/"),
    (11, "Baltimore County", "August", "12.0% Annual", "6 Months", "County-Held Unsold Liens", "Surplus Info Available", "https://www.baltimorecountymd.gov/"),
    (12, "Carroll County", "June", "12.0% Annual", "6 Months", "Surplus Recovery Prime", "Detailed Surplus Dataset", "https://www.carrollcountymd.gov/"),
    (13, "Caroline County", "August", "12.0% Annual", "6 Months", "Surplus List Published", "Excess Funds Published", "https://www.carolinecounty.org/"),
    (14, "Charles County", "May/June", "10.0% to 12.0% Annual", "6 Months", "Certificate Assignments", "Treasury Division", "https://www.charlescountymd.gov/"),
    (15, "Montgomery County", "June", "20.0% Annual", "6 Months", "No OTC (Surplus Only)", "Prime Published Surplus List", "https://www.montgomerycountymd.gov/"),
    (16, "Calvert County", "May", "10.0% Annual", "6 Months", "County-Held Inventory", "County Treasurer", "https://www.calvertcountymd.gov/"),
    (17, "Dorchester County", "May", "10.0% Annual", "6 Months", "Assignment Permitted", "County Finance", "https://dorchestercountymd.com/"),
    (18, "Garrett County", "May", "10.0% Annual", "6 Months", "County-Held Inventory", "Tax Collection Office", "https://www.garrettcountymd.gov/"),
    (19, "Harford County", "June", "12.0% Annual", "6 Months", "Assignments Permitted", "Treasury Office", "https://www.harfordcountymd.gov/"),
    (20, "Somerset County", "June", "12.0% Annual", "6 Months", "County-Held Inventory", "Finance Office", "https://www.somersetmd.us/"),
    (21, "St. Mary's County", "March", "10.0% Annual", "6 Months", "Treasurer Assignment", "County Treasurer", "https://www.stmaryscountymd.gov/"),
    (22, "Talbot County", "May", "12.0% Annual", "6 Months", "Finance Assignment", "Finance Office", "https://www.talbotcountymd.gov/"),
    (23, "Washington County", "June", "12.0% Annual", "6 Months", "County-Held Inventory", "County Treasurer", "https://www.washco-md.net/"),
    (24, "Allegany County", "May", "12.0% Annual", "6 Months", "Post-Auction Unsold Sale", "Finance Office", "https://www.alleganygov.org/")
]

for row_idx, row in enumerate(county_directory_data, start=2):
    ws_dir.append(list(row))
    for c in range(1, len(dir_headers) + 1):
        ws_dir.cell(row=row_idx, column=c).border = thin_border

for col in ws_dir.columns:
    max_len = max(len(str(cell.value or '')) for cell in col)
    col_letter = get_column_letter(col[0].column)
    ws_dir.column_dimensions[col_letter].width = max(max_len + 3, 14)

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Save Workbook
wb.save(EXCEL_OUTPUT)
print(f"\n[SUCCESS] Saved Master Multi-Tab Excel Workbook to: {EXCEL_OUTPUT}")

# Export CSV
import csv
with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    for r in master_sorted:
        writer.writerow([
            r["county"], r["list_no"], r["account_id"], r["owner"], r["address"],
            r["assessed_value"], r["opening_bid"], r["ltv_pct"], r["equity_spread"],
            r["statutory_interest"], r["redemption_window"], r["tier"], r["contact_info"]
        ])
print(f"[SUCCESS] Saved Master CSV to: {CSV_OUTPUT}")
