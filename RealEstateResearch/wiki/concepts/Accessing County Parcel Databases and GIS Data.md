---
category: concept
tags: [gis-data, open-data, arcgis-rest-api, foia-requests, propstream, parcel-scraping, virginia, hampton-roads]
created: 2026-09-02
updated: 2026-09-02
sources:
  - "[Hampton Roads Off-Market Campaign Playbook and GIS Query Pack](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/wiki/synthesis/Hampton%20Roads%20Off-Market%20Campaign%20Playbook%20and%20GIS%20Query%20Pack.md)"
  - "[Virginia Geographic Information Network (VGIN)](https://vgin.vdem.virginia.gov)"
  - "[Chesapeake GIS Open Data Hub](https://data-chesapeake.opendata.arcgis.com)"
---

# Accessing County Parcel Databases and GIS Data

A practical guide explaining the **four methods** real estate investors use to access, query, and export county parcel databases for off-market deal sourcing in Virginia and nationwide.

---

## 🧭 The 4 Data Access Methods

```mermaid
graph TD
    A[Accessing Parcel Databases] --> B[Method 1: County Open Data & ArcGIS REST APIs<br>100% Free | Instant Download / Python API]
    A --> C[Method 2: Commercial Aggregators<br>PropStream / Prycd / DealMachine<br>Point-and-Click GUI + 1-Click Skip Tracing]
    A --> D[Method 3: FOIA Public Records Request<br>Official Bulk County Tax Roll CSV from Assessor]
    A --> E[Method 4: Statewide GIS Portals<br>Virginia VGIN Statewide Parcel Layer]
```

---

## 🌐 Method 1: Free County Open Data Portals & ArcGIS REST APIs

Most modern counties and cities host their entire real estate parcel layer on **ArcGIS Open Data Hubs** or **ESRI REST FeatureServers**, which are 100% free and open to the public.

### How to Access:

#### 1. City of Chesapeake
* **Open Data Portal**: [Chesapeake Open Data Hub](https://data-chesapeake.opendata.arcgis.com)
* **How to Query**:
  1. Search for **"Parcels"** or **"Real Estate Assessment"**.
  2. Click the **Data / Table** tab.
  3. Apply visual filters: `Improvement Value = 0`, `Zoning = R-6, R-8`, `Lot Size <= 21780`.
  4. Click **Download** $\to$ Select **CSV** or **GeoJSON**.

#### 2. City of Hampton
* **Open Data Portal**: [Hampton Open Data Portal](https://hampton-hampton.opendata.arcgis.com)
* Search for **"Real Estate Parcels"** $\to$ Filter by building value `$0` and target neighborhoods $\to$ Export CSV.

#### 3. Virginia Statewide VGIN Parcel Portal
* **Portal**: [Virginia Geographic Information Network (VGIN)](https://vgin.vdem.virginia.gov)
* The State of Virginia maintains a standardized **Statewide Parcel Dataset** combining all 133 counties and independent cities into a unified downloadable shapefile/database.

---

## 💻 Method 1B: Querying ArcGIS REST API via Python (Automated)

You can run SQL queries directly against county REST servers from a simple Python script without downloading large gigabyte files.

```python
import requests
import pandas as pd

# Example: Querying a Municipal ArcGIS REST Endpoint
REST_URL = "https://gis.cityofchesapeake.net/arcgis/rest/services/Parcels/MapServer/0/query"

params = {
    "where": "ASSESSED_IMPROVEMENT_VALUE = 0 AND LOT_AREA_SQFT >= 3000 AND LOT_AREA_SQFT <= 21780",
    "outFields": "PARCEL_ID,OWNER_NAME,PROPERTY_ADDRESS,MAILING_ADDRESS,MAILING_CITY,MAILING_STATE,MAILING_ZIP,ZONING,LOT_AREA_SQFT,ASSESSED_LAND_VALUE",
    "f": "json",
    "resultRecordCount": 1000,
    "returnGeometry": "false"
}

response = requests.get(REST_URL, params=params)
data = response.json()

# Extract attributes to DataFrame & export CSV
records = [feature["attributes"] for feature in data.get("features", [])]
df = pd.DataFrame(records)
df.to_csv("chesapeake_vacant_lots.csv", index=False)
print(f"Exported {len(df)} vacant lots to CSV.")
```

---

## ⚡ Method 2: Commercial Real Estate Platforms (Fastest & Easiest)

For investors who prefer a clean, point-and-click graphical interface with **built-in skip tracing** (instant phone numbers and emails), commercial platforms aggregate and update all county assessor rolls daily:

| Platform | Best For | Typical Pricing | Key Features |
| :--- | :--- | :--- | :--- |
| **PropStream** ([propstream.com](https://propstream.com)) | Nationwide parcel filtering & skip tracing | ~$99/month | Filter by vacant land, equity, absentee status, tax delinquency; 1-click skip tracing. |
| **Prycd** ([prycd.com](https://prycd.com)) | Specialized land investors | Usage-based | Automates land pricing and blind offer generation directly from county records. |
| **DealMachine** ([dealmachine.com](https://dealmachine.com)) | Driving for dollars & map list building | ~$49–$99/mo | Interactive map view of parcel boundaries and owner contact cards. |
| **BatchLeads** ([batchleads.io](https://batchleads.io)) | High-volume direct mail & phone lists | ~$79–$119/mo | Advanced list stacking (filtering vacant + tax delinquent + out of state). |

### Step-by-Step in PropStream:
1. Type `Chesapeake, VA` (or `Hampton, VA`, `York County, VA`, `Poquoson, VA`) in the search bar.
2. Click **Filter** $\to$ Select **Property Characteristics**: `Vacant Land`.
3. Set **Lot Size**: `3,000 sq ft to 21,780 sq ft (0.50 Acres)`.
4. Set **Ownership Info**: `Owner Type = Individual`, `Absentee Owner = Any / Out of State`, `Years of Ownership >= 5`.
5. Set **Financials**: `Estimated Value <= $90,000`.
6. Click **Add to List** $\to$ Export CSV or click **Skip Trace** to pull mobile phone numbers immediately.

---

## 🏛️ Method 3: FOIA Public Records Request (Bulk Official Tax Roll)

Under the **Virginia Freedom of Information Act (VA Code § 2.2-3700 et seq.)**, every Virginia city assessor must provide the complete public real estate tax assessment roll upon written request.

### Email Request Template to City Assessor:

```text
To: assessor@cityofchesapeake.net (or assessor@hampton.gov / assessor@yorkcounty.gov)
Subject: FOIA Public Records Request - Real Property Assessment Master File (Electronic)

Dear Assessor's Office,

Pursuant to the Virginia Freedom of Information Act (Va. Code § 2.2-3700 et seq.), I am requesting an electronic copy of the current Real Property Assessment Master File / Real Estate Tax Roll for the City of [Chesapeake / Hampton / York County].

Please provide the record in electronic spreadsheet format (CSV, Excel, or pipe-delimited text) including the following data fields:
1. Parcel Identification Number (PIN / Account ID)
2. Owner Name(s) and Mailing Address (Street, City, State, Zip)
3. Property Physical Address
4. Property Class / Land Use Code (specifically identifying Vacant Land)
5. Zoning Classification
6. Lot Area (Square Feet or Acreage)
7. Assessed Land Value and Assessed Improvement/Building Value
8. Total Assessed Value

Please provide this file via email download or secure link. If there are statutory administrative copying fees, please advise prior to fulfillment.

Thank you for your assistance.

Sincerely,

Chetan Thakur
[Your Phone Number]
[Your Mailing Address]
```

---

## 🏛️ Statewide GIS & Cadastre Infrastructure (Mid-Atlantic)

| Jurisdiction | Primary Statewide Platform | Key Capabilities & Data Layers |
| :--- | :--- | :--- |
| **Maryland** | **MD iMAP / SDAT MapServer**<br>[imap.maryland.gov](https://imap.maryland.gov/) | Statewide cadastre covering all 24 jurisdictions. REST MapServer endpoint queries parcel geometries, assessments, building sqft, year built, and land use codes. |
| **Virginia** | **VGIN Statewide Parcel Dataset**<br>[vgin.vdem.virginia.gov](https://vgin.vdem.virginia.gov) | Unified parcel geometry covering 95 counties and 38 independent cities. |
| **New Jersey** | **NJGIN Property Explorer**<br>[nj.gov/njgin/edata/parcels/](https://www.nj.gov/njgin/edata/parcels/) | Centralized Block/Lot viewer integrated with the MOD-IV state property tax assessment database. |
| **Delaware** | **Delaware FirstMap**<br>[firstmap.delaware.gov](https://firstmap.delaware.gov/) | Enterprise GIS covering New Castle, Kent, and Sussex counties with zoning overlays and coastal wetland buffers. |

---

## 📊 Summary: Which Method Should You Use?

| Scenario | Recommended Access Method | Time to Data | Cost |
| :--- | :--- | :--- | :--- |
| **I want phone numbers and immediate mailing letters today** | **Method 2: PropStream / Prycd** | **5 minutes** | ~$99/mo (Free trials available) |
| **I want 100% free official records and know how to use Excel** | **Method 1: County Open Data Hubs** | **15 minutes** | **$0.00 Free** |
| **I want the complete master tax roll for an entire county** | **Method 3: FOIA Request to Assessor** | **2–5 business days** | **$0–$25** |
| **I want automated programmatic scraping via scripts** | **Method 1B: ArcGIS REST API (Python)** | **Instant** | **$0.00 Free** |
| **I want regional parcel mapping across MD, VA, NJ, DE** | **Method 4: Statewide Cadastre Portals (MD iMAP, NJGIN, FirstMap, VGIN)** | **10 minutes** | **$0.00 Free** |

---

## 🔗 Related Wiki Pages
* [[Regional Mid-Atlantic Tax Sale Master Directory - MD VA NJ DE]]
* [[Delaware Monition and Tax Deed Market]]
* [[New Jersey Municipal Tax Sale Market]]
* [[Virginia Judicial Tax Deed and Independent Cities Market]]
* [[Hampton Roads Off-Market Campaign Playbook and GIS Query Pack]]
* [[Off-Market Deal Sourcing and Candidate Parcels - Hampton Roads VA]]
* [[Buy Box - Hampton Roads Infill Land and Lots]]
* [[Land Search Platforms and Deal Sourcing]]
* [[Virginia Land and Tax Deed Buy Box]]

