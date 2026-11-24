---
category: market
tags: [illinois, tax-liens, 35-ilcs-200, pa-103-0555, cook-county, dupage-county, lake-county, kane-county, will-county, iltaxsale, telegram-bot, arcgis-api, socrata]
created: 2026-11-24
updated: 2026-11-24
sources:
  - "[Illinois Parcel Engine (31 Counties)](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/illinois_parcel_engine.py)"
  - "[Multi-State Parcel Router](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/multi_state_parcel_engine.py)"
  - "[Tax Lien State Directory - 14 Investor Certificate Jurisdictions](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/wiki/synthesis/Tax%20Lien%20State%20Directory%20-%2014%20Investor%20Certificate%20Jurisdictions.md)"
  - "Illinois Property Tax Code (35 ILCS 200/21-215, 21-350, 21-355, 9-145; Public Act 103-0555 / SB 1675 eff. Jan 1, 2024)"
  - "Tax Lien School Vault — Illinois 31 Priority Counties Reference Links (provided Nov 24, 2026)"
---

# Illinois Tax Lien Market — 31 Priority Counties

Comprehensive market handbook, statutory underwriting framework (**35 ILCS 200**), and live Telegram bot / GIS API directory covering **31 priority Illinois counties** (`22` counties connected to **live zero-login ArcGIS REST / Socrata Open Data APIs** + `9` counties wired with direct official Assessor / DevNet Wedge / Treasurer deep-links and automatic tax-sale export indexing).

---

## ⚖️ Statutory Tax Lien Framework (`35 ILCS 200`) & 2024 Rate Reform

> [!IMPORTANT] Conflict Resolution — Pre-2024 (`36%/yr`) vs. Current Statutory Cap (`18%/yr` Max under `P.A. 103-0555`)
> * **Historical / Tax Lien School Legacy Materials:** Older guides (including Tax Lien School's URL slug `illinois-the-best-tax-lien-state-with-36percent-return-on-investment`) reference Illinois's historic statutory maximum of **`18%` per 6-month period (`36%/yr`)**, which applied strictly to tax sale certificates issued **prior to January 1, 2024**.
> * **Current Statutory Law (2024–2026+, `Public Act 103-0555` / `SB 1675` amending `35 ILCS 200/21-215`):** Effective **January 1, 2024**, Illinois lowered the statutory maximum penalty bid cap statewide (both Cook County and all downstate counties) to **`9%` per 6-month period (`18%/yr` annualized max)**. Both figures are preserved here so historical underwriting comparisons remain clear while live bidding uses current 2026 statute.

| Statutory Parameter | Current 2026 Illinois Law (`35 ILCS 200`) | Investor Takeaway vs. Colorado |
| :--- | :--- | :--- |
| **Bidding Format** | **Bid-Down Penalty %** (`9%` down to `0%` per 6-mo period) | **Zero non-refundable surplus/premium!** Unlike Colorado (`\$1,239.93` non-refundable surplus drag), 100% of your principal in Illinois is returned upon redemption. |
| **Step-Up Penalty Schedule (`35 ILCS 200/21-355`)** | Winning bid % applies **every 6 months** as a step jump (Day 1 -> `1×` bid %, Mo 7 -> `2×`, Mo 13 -> `3×`, Mo 19 -> `4×`, Mo 25 -> `5×`) | At a `9%` winning bid, even a Day-10 redemption pays the full **`9%`**. A Month-13 redemption pays **`27%`**. |
| **Subsequent Taxes ("Sub-Taxes")** | **`12%` flat per year** (`35 ILCS 200/21-355(c)`) | Paying Year 2 & Year 3 taxes locks in a solid `12%/yr` flat rate even if the initial auction was bid down low. |
| **Redemption Windows (`35 ILCS 200/21-350`)** | **2.5 Years** (`1–6` unit residential) \| **2 Years** (vacant / other / `7+` units) \| **6 Months** (commercial/industrial or vacant non-farm `2+` yrs delinquent) | Shorter redemption on commercial & vacant delinquent parcels accelerates deed / payoff turnover. |
| **Assessment Ratio (`35 ILCS 200/9-145`)** | **Downstate (30 counties):** `33.33%` of Fair Cash Value (`FMV ≈ Assessed × 3`)<br>**Cook County:** `10%` Class 2 Residential (`FMV ≈ AV × 10`), `25%` Class 5 Commercial (`FMV ≈ AV × 4`) | Our live bot (`illinois_parcel_engine.py`) automatically converts each county's EAV/Assessed Value to Estimated Full Market Value (`FMV`). |
| **County Trustee OTC / Unsold Program** | **Joseph E. Meyer & Associates** ([ILTaxSale.com](https://iltaxsale.com/)) manages Trustee tax deeds & assignable delinquent certificates for ~`94` of `102` Illinois counties | Great secondary acquisition channel for OTC assignable certificates and sealed-bid Trustee tax deeds without live auction bid-down competition. |
| **Take Notice & Judicial Tax Deed** | Strict statutory notices (`35 ILCS 200/22-5` within 4 mo 15 days of sale + `22-10` Take Notice 3–6 mos prior to expiration) + Circuit Court Petition for Tax Deed | Illinois is a **strict-compliance notice state** — retain an Illinois tax-deed attorney before Year 2 if pursuing a deed. |

---

## 🗺️ Master 31-County Illinois Directory & Live Bot Integration

All 31 counties below are live inside [`illinois_parcel_engine.py`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/illinois_parcel_engine.py), [`multi_state_parcel_engine.py`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/multi_state_parcel_engine.py), [`real_estate_telegram_bot.py`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/real_estate_telegram_bot.py), and [`app.py`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/app.py) (`/parcel?q=...` & `/api/il/counties`).

### A. 22 Live Direct-API Counties (Real-Time Zero-Login GIS / Socrata Enrichment)

| # | County | Region | Telegram Command | PIN Format (`Digits`) | Live Data API Source | Official Links |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Adams** | Western IL (Quincy) | `/adams <PIN>` | `01-00-001-000-00` (`12`) | ArcGIS `ParcelsOnlineMap` (`21` fields: Owner, TaxDue, Val, Acres) | [DevNet](https://adamsil.devnetwedge.com/) \| [Treasurer](https://www.adamscountyil.gov/government/departments/treasurer) |
| 2 | **Boone** | Northern IL (Belvidere) | `/boone <PIN>` | `07-31-400-006` (`10`) | ArcGIS `Assessment_Parcels` (`13` fields: PIN, Address, Acres, Legal) | [DevNet](https://booneil.devnetwedge.com/) \| [Treasurer](https://www.boonecountyil.gov/departments/treasurer) |
| 3 | **Cook** | Chicagoland (Chicago) | `/cook <PIN or St>` | `33-31-402-022-0000` (`14`) | **Cook Socrata 2026** (`3723-97qp`, `uzyt-m557`, `nj4t-kc8j`, `x54s-btds`, `wvhk-k5uv`) | [Assessor](https://www.cookcountyassessor.com/) \| [Treasurer](https://www.cookcountytreasurer.com/) |
| 4 | **DeKalb** | Northern IL (Sycamore) | `/dekalb <PIN>` | `01-01-100-001` (`10`) | ArcGIS `DeKalbIL_Parcels` (`29` fields: Owner, TaxBilled, EAV, Zoning) | [DevNet](https://dekalbil.devnetwedge.com/) \| [Treasurer](https://dekalbcounty.org/departments/treasurer/) |
| 5 | **DuPage** | Chicagoland Collar | `/dupage <PIN>` | `06-15-117-021` (`10`) | ArcGIS `ParcelsWithRealEstateCC` (`86` fields: FCV, Tax, Owner, Legal) | [Lookup](https://www.dupagecounty.gov/propertylookup/) \| [Treasurer](https://www.dupagecounty.gov/government/county_offices/treasurer/) |
| 6 | **Grundy** | Outer Collar (Morris) | `/grundy <PIN>` | `01-01-100-001` (`10`) | ArcGIS `CountyParcelsTotalValue_SPIE` (`29` fields: Farm/NonFarm Val, Owner) | [DevNet](https://grundyil.devnetwedge.com/) \| [Treasurer](https://www.grundycountyil.gov/treasurer/) |
| 7 | **Henry** | NW IL (Cambridge) | `/henry <PIN>` | `24-28-427-010` (`10`) | ArcGIS `Parcel_Henry` (`38` fields, 2026: Land/Imp, EAV, Tax, Legal) | [DevNet](https://henryil.devnetwedge.com/) \| [Treasurer](https://www.henrycty.com/195/Treasurer) |
| 8 | **Kane** | Chicagoland Collar | `/kane <PIN>` | `01-01-100-001` (`10`) | ArcGIS `KaneCo_IL_Parcels` (`48` fields: Owner, Acres, Doc#, TIF, Districts) | [DevNet](https://kaneil.devnetwedge.com/) \| [Treasurer](https://www.kanecountytreasurer.org/) |
| 9 | **Kendall** | Collar (Yorkville/Oswego) | `/kendall <PIN>` | `01-06-100-006` (`10`) | ArcGIS `Parcels___Tax_District_Join` (`28` fields: Districts, TaxCode, GPS) | [DevNet](https://kendallil.devnetwedge.com/) \| [Treasurer](https://www.kendallcountyil.gov/offices/treasurer) |
| 10 | **Lake** | North Collar (Waukegan) | `/lake <PIN>` | `01-12-301-005` (`10`) | ArcGIS `OpenData_ParcelPolygons` (`24` fields: Taxpayer, Situs, Legal, GPS) | [Assessor](https://tax.lakecountyil.gov/) \| [Tax Sale](https://www.lakecountyil.gov/361/Tax-Sale-Information) |
| 11 | **LaSalle** | North-Central (Ottawa) | `/lasalle <PIN>` | `33-36-109-025` (`10`) | ArcGIS `LandValuesV2` (`108` fields, 2026: Val, Sales, YrBuilt, SqFt, Legal) | [Assessor](https://lasallecountyil.gov/249/Supervisor-of-Assessments) \| [Treasurer](https://lasallecountyil.gov/252/Treasurer) |
| 12 | **Macon** | Central IL (Decatur) | `/macon <PIN>` | `04-12-23-230-040` (`12`) | ArcGIS `SRS2026Parcels` (`37` fields, 2026: Owner, Val, Sales, Zoning) | [Assessor](https://www.maconcounty.illinois.gov/offices/supervisor-of-assessments/) \| [Treasurer](https://www.maconcounty.illinois.gov/offices/treasurer/) |
| 13 | **Madison** | Metro East (Edwardsville) | `/madison <PIN>` | `07-1-11-02-00-000-002` (`15`) | ArcGIS `County_Parcels/12` (`27` fields: Owner, Situs, Mailing, Acres) | [DevNet](https://madisonil.devnetwedge.com/) \| [Tax Sale](https://www.madisoncountyil.gov/departments/treasurer/tax_sale_information.php) |
| 14 | **McHenry** | NW Collar (Woodstock) | `/mchenry <PIN>` | `01-01-301-003` (`10`) | ArcGIS `Parcels/0` (`11` fields: PIN, Address, LandUse, TaxStatus, GPS) | [DevNet](https://mchenryil.devnetwedge.com/) \| [Tax Sale](https://www.mchenrycountyil.gov/departments/treasurer/tax-sale) |
| 15 | **McLean** | Central (Bloomington) | `/mclean <PIN>` | `14-25-277-020` (`10`) | ArcGIS `Cadastral_Web` (`22` fields, 2026: Owner, Acres, Direct Links) | [DevNet](https://mcleanil.devnetwedge.com/) \| [Treasurer](https://www.mcleancountyil.gov/117/Treasurer) |
| 16 | **Peoria** | Central IL (Peoria) | `/peoria <PIN>` | `17-26-329-017` (`10`) | ArcGIS `Tax_Parcels/5` (`59` fields: Owner, Val, YrBuilt, Beds/Baths) | [Tax Inquiry](https://www.peoriacounty.gov/386/Property-Tax-Inquiry) \| [Treasurer](https://www.peoriacounty.gov/376/Treasurer) |
| 17 | **Rock Island** | Quad Cities (Moline) | `/rockisland <PIN>` | `01-33-300-004` (`10`) | ArcGIS `Parcels/0` (`83` fields: EMV, EAV, Sales, Floodway, Zoning, GPS) | [DevNet](https://rockislandil.devnetwedge.com/) \| [Treasurer](https://www.rockislandcountyil.gov/252/Treasurer) |
| 18 | **St. Clair** | Metro East (Belleville) | `/stclair <PIN>` | `21-35.0-300-010` (`11`) | ArcGIS `SCC_parcel_map_data/29` (`99` fields: Owner, Val, Legal, Districts) | [DevNet](https://stclairil.devnetwedge.com/) \| [Treasurer](https://www.co.st-clair.il.us/departments/treasurer) |
| 19 | **Tazewell** | Central (Pekin/E. Peoria) | `/tazewell <PIN>` | `23-23-22-307-010` (`12`) | ArcGIS `TazCo_Parcels_WithOwner/1` (`87` fields: Val, TaxBilled, **Inst1/2 Paid Dates!**) | [DevNet](https://tazewellil.devnetwedge.com/) \| [Treasurer](https://www.tazewell-il.gov/191/Treasurer) |
| 20 | **Vermilion** | East-Central (Danville) | `/vermilion <PIN>` | `13-33-100-004` (`10`) | ArcGIS `Tax_Parcels_Public` (`26` fields: Owner, Acres, Legal, SideLot flags) | [DevNet](https://vermilionil.devnetwedge.com/) \| [Treasurer](https://www.vercounty.org/treasurer/) |
| 21 | **Whiteside** | NW IL (Sterling/Morrison) | `/whiteside <PIN>` | `22-36-400-002` (`10`) | ArcGIS `Tax_Parcels_Ver_2` (`70` fields: Val, TaxOwed, YrBuilt, WedgeURL) | [DevNet](https://whitesideil.devnetwedge.com/) \| [Treasurer](https://www.whitesidecountyil.gov/196/Treasurer) |
| 22 | **Will** | South Collar (Joliet) | `/will <PIN>` | `19-09-14-205-002-0000` (`16`) | ArcGIS `HistoricParcels/Parcels_2022` (PIN Geometry, Acres, GPS) | [SOA Search](https://willcountysoa.com/ParcelSearch) \| [Treasurer](https://www.willcountytreasurer.com/) |

### B. 9 Portal-Linked Counties (PIN Parser + Direct DevNet / Assessor Deep-Links + Upload Auto-Indexing)

| # | County | Region | Telegram Command | PIN Format (`Digits`) | Official Portals |
| :---: | :--- | :--- | :--- | :--- | :--- |
| 23 | **Champaign** | East-Central (Champaign-Urbana) | `/champaign <PIN>` | `46-21-07-302-014` (`12`) | [DevNet Wedge](https://champaignil.devnetwedge.com/) \| [Tax Sale](https://www.champaigncountyil.gov/treasurer/tax-sale) \| [CCGISC](https://maps.ccgisc.org/public/) |
| 24 | **Jackson** | Southern IL (Carbondale) | `/jackson <PIN>` | `15-21-201-001` (`10`) | [DevNet Wedge](https://jacksonil.devnetwedge.com/) \| [Treasurer](https://www.jacksoncounty-il.gov/government/departments-l-z/treasurer) |
| 25 | **Kankakee** | South Chicagoland | `/kankakee <PIN>` | `16-09-32-301-001` (`12`) | [DevNet Wedge](https://kankakeeil.devnetwedge.com/) \| [Treasurer](https://www.k3county.net/treasurer) \| [K3GIS](https://k3gis.com/) |
| 26 | **Knox** | Western IL (Galesburg) | `/knox <PIN>` | `99-10-301-001` (`10`) | [DevNet Wedge](https://knoxil.devnetwedge.com/) \| [Treasurer](https://www.co.knox.il.us/treasurer/) |
| 27 | **Ogle** | Northern IL (Oregon/Rochelle) | `/ogle <PIN>` | `16-03-401-001` (`10`) | [DevNet Wedge](https://ogleil.devnetwedge.com/) \| [Treasurer](https://www.oglecountyil.gov/departments/treasurer/index.php) |
| 28 | **Sangamon** | Central IL (Springfield) | `/sangamon <PIN>` | `14-28.0-401-012` (`11`) | [Tax Lookup](https://tax.co.sangamon.il.us/) \| [Treasurer](https://sangamonil.gov/departments/s-z/treasurer) \| [SANGIS](https://www.sangis.org/) |
| 29 | **White** | Southeastern IL (Carmi) | `/white <PIN>` | `13-13-101-001` (`10`) | [DevNet Wedge](https://whiteil.devnetwedge.com/) \| [Treasurer](https://www.whitecounty-il.gov/treasurer) |
| 30 | **Williamson** | Southern IL (Marion/Herrin) | `/williamson <PIN>` | `06-18-301-001` (`10`) | [DevNet Wedge](https://williamsonil.devnetwedge.com/) \| [Treasurer](https://www.williamsoncountyil.gov/treasurer/) |
| 31 | **Winnebago** | Northern IL (Rockford) | `/winnebago <PIN>` | `11-23-456-007` (`10`) | [Tax Lookup](https://tax.wincoil.gov/) \| [Treasurer](https://wincoil.gov/departments/treasurer) \| [WinGIS](https://maps.wingis.org/) |

---

## 🤖 Telegram Bot & Live Web Usage Guide

1. **View All 31 Counties:** Send `/il` or `/illinois` in `@RealestateResearch_bot`.
2. **Query by Specific County Command:** Send `/cook 33-31-402-022-0000`, `/dupage 06-15-117-021`, `/peoria 17-26-329-017`, `/tazewell 23-23-22-307-010`, `/stclair 21-35.0-300-010`, or `/cook 3111 231ST ST`.
3. **Zero-Prefix Auto-Routing (Just Paste a PIN!):** Sending a raw Illinois PIN (`33-31-402-022-0000`, `06-15-117-021`, `21-35.0-300-010`, `07-1-11-02-00-000-002`) automatically detects the Illinois PIN pattern and fans out across live county APIs without touching Maryland SDAT.
4. **Zero-Login Mobile Web Dossier:** Every Telegram Illinois dossier includes a clickable `/parcel?q=<County> IL <PIN>` link hosted on Render, plus `/api/il/counties` JSON endpoint.
5. **Bulk Auction List Uploads:** Drop any Illinois county delinquent tax sale `.xlsx`, `.csv`, or `.pdf` into `raw/` (named e.g. `2026 Cook County Illinois Tax Lien Sale - Full Export.xlsx`) or directly into Telegram chat to automatically index face amounts and merge with live GIS valuations.

---

## 🔗 Related Wiki Pages
* [[Real Estate Research Master Mind Map]]
* [[Tax Lien State Directory - 14 Investor Certificate Jurisdictions]]
* [[Over-The-Counter Tax Lien Sourcing Portals and Direct Links]]
* [[Portfolio - 2026 Tax Lien Certificates Owned]]
* [[Synthesis - Maryland SDAT and Tax Lien Telegram Intelligence Bot]]
