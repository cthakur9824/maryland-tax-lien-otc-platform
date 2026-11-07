import fitz
import re
import json

pdf_path = r"c:\Obsedian\RealEstateResearch\RealEstateResearch\raw\Anne-Arundell-list-of-liens.pdf"
doc = fitz.open(pdf_path)

all_records = []

for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Pattern to match table row: LIST# (1-4 digits) ACCOUNT# (12 digits)
    # Let's inspect line sequences
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match list# and account#
        # Sometimes list# and account# are on the same line or separate
        match = re.match(r'^(\d+)\s+(\d{12})$', line)
        if match:
            list_no = int(match.group(1))
            acct_no = match.group(2)
            # Next lines should be owner, assessment, bid amount, sale amount, bid premium, interest, total due
            if i + 7 < len(lines):
                owner = lines[i+1]
                assessment_str = lines[i+2]
                bid_str = lines[i+3]
                sale_str = lines[i+4]
                premium_str = lines[i+5]
                interest_str = lines[i+6]
                total_str = lines[i+7]
                
                try:
                    assessment = float(assessment_str.replace(',', ''))
                    bid_amount = float(bid_str.replace(',', ''))
                    total_due = float(total_str.replace(',', ''))
                    
                    # Calculate Loan-to-Value (Lien-to-Value Ratio)
                    ltv = (total_due / assessment) * 100 if assessment > 0 else 999.0
                    
                    all_records.append({
                        "list_no": list_no,
                        "account_no": acct_no,
                        "owner": owner,
                        "assessment": assessment,
                        "bid_amount": bid_amount,
                        "bid_premium": float(premium_str.replace(',', '')),
                        "interest": float(interest_str.replace(',', '')),
                        "total_due": total_due,
                        "ltv_pct": round(ltv, 2)
                    })
                    i += 8
                    continue
                except Exception as e:
                    pass
        i += 1

print(f"Parsed {len(all_records)} lien records from PDF.")
# Sort by assessment descending and LTV ascending
print("\nSample top assessed records:")
top_assessed = sorted(all_records, key=lambda x: x["assessment"], reverse=True)[:10]
for r in top_assessed:
    print(f"List #{r['list_no']} | Acct: {r['account_no']} | Owner: {r['owner']} | Assessment: ${r['assessment']:,.0f} | Total Due: ${r['total_due']:,.2f} | LTV: {r['ltv_pct']}%")

# Save parsed records to json
with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_parsed_liens.json", "w") as f:
    json.dump(all_records, f, indent=2)
