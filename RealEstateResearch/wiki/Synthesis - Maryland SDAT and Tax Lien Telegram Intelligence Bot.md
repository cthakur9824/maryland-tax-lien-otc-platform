# Synthesis - Maryland SDAT and Tax Lien Telegram Intelligence Bot

**Engine Type**: Automated Real Estate Research, SDAT Cadastre Scraper, and Telegram Interaction Bot  
**Target Coverage**: All 24 Maryland Counties & Jurisdictions  
**Primary Integration**: Maryland MD iMAP ArcGIS REST Services + Anne Arundel County Munis Tax Portal + Obsidian Knowledge Base  
**Telegram Bot Handle**: `@RealestateResearch_bot`  
**Date Created**: 2026-09-10

---

## 🏗️ Architecture & Pipeline Overview

The **Maryland Real Estate & Tax Lien Bot** connects mobile Telegram messaging to authoritative Maryland land databases, enabling real-time property intelligence and automated Obsidian wiki archiving:

```
┌─────────────────────────────────────────────────────────────┐
│                      TELEGRAM CLIENT                        │
│            User sends: "1883 Cedar Dr, Severn, MD"          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 real_estate_telegram_bot.py                 │
│              (Long-polling Telegram Listener)               │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│       sdat_engine.py         │ │    tax_lien_checker.py     │
│   (MD iMAP Cadastre REST)    │ │   (County Munis Portals)   │
├──────────────────────────────┤ ├────────────────────────────┤
│ • APN / Account Identifier   │ │ • Billed Owner of Record   │
│ • Acreage & Sq Ft Dimensions │ │ • Annual Tax Bills         │
│ • Zoning (R2, R5, Commercial)│ │ • Delinquency & Tax Sales  │
│ • Liber / Folio Deed History │ │ • Statutory Redemption     │
│ • Last Sale Date & Price     │ │                            │
│ • Absentee Owner Detection   │ │                            │
└──────────────┬───────────────┘ └────────────┬───────────────┘
               │                              │
               └──────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      wiki_exporter.py                       │
│     • Ingests dossier into `wiki/Analysis - <Address>.md`   │
│     • Appends entry to `index.md` and logs to `log.md`      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Core System Modules

1. **`sdat_engine.py`**:
   * Official Statewide Endpoint: `https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query`
   * Queries 114+ parcel fields without Cloudflare blocking.
   * Auto-detects absentee owners by comparing premise address vs owner mailing address.

2. **`tax_lien_checker.py`**:
   * Queries county tax portals including **Anne Arundel County Munis Self-Service** (`aacounty.munisselfservice.com`).
   * Extracts live property tax billing records, billed ownership, and tax sale flags.

3. **`wiki_exporter.py`**:
   * Implements LLM Wiki Maintainer standards.
   * Automatically creates standard Obsidian wikilinks, formats tables and alert blocks, updates master `index.md`, and writes timestamped audit entries to `log.md`.


4. **`real_estate_telegram_bot.py`**:
   * Resilient async polling loop + 12-hour background County OTC Auto-Sync daemon.
   * Accepts direct file uploads (`.csv`, `.xlsx`, `.pdf`, `.json`) in chat to ingest new Over-The-Counter county lists on the fly.
   * Formats structured Markdown cards with emojis, clickable SDAT links, Grade A/B Title Confluence badges, and offer breakdowns.

5. **`otc_manager.py`**:
   * **Universal OTC File Importer** (`import_otc_file`): Normalizes any county `.csv`, `.xlsx`, `.pdf`, or `.json` OTC list into `raw/maryland_master_otc_liens.json` and `Maryland_24_Counties_Tax_Lien_OTC_Master_2026.csv`, then automatically runs SDAT + Title Confluence grading on low-LTV candidates.
   * **Intelligent County Website Crawler** (`sync_all_county_websites`): Automatically crawls official Maryland county tax sale portals (Anne Arundel, Prince George's, Wicomico, Worcester, Queen Anne's, Cecil, Kent, Caroline, Carroll, Baltimore City) to discover, download, and ingest the latest unassigned OTC PDF lists into `raw/auto_sync/` (expanding the live database to **3,296 OTC parcels** across 7 active OTC counties).

6. **`app.py`**:
   * **Live Web Platform & REST API** (`http://localhost:8080` and cloud-ready via `Procfile` + `railway.json`).
   * Features an interactive Grade A & B deals browser, 3,296-parcel Master OTC directory, drag-and-drop OTC File Importer (`POST /api/import`), one-click County Website Auto-Sync (`POST /api/sync`), and live SDAT + Title Confluence lookup (`GET /api/lookup`).

---

## 📱 Interactive Telegram Command Reference

| Command | Usage Example | Function |
| :--- | :--- | :--- |
| **`/start` or `/help`** | `/help` | Displays command list and instructions. |
| **`Direct Address`** | `1883 Cedar Dr, Severn, MD` | Automatically parses and runs full property lookup. |
| **`/lookup <address>`** | `/lookup 1883 Cedar Dr, Severn` | Explicit address lookup on SDAT. |
| **`/parcel <APN>`** | `/parcel 020474604872500` | Direct query by Maryland APN / Account ID. |
| **`/tax <query>`** | `/tax 1883 Cedar Dr` | Deep search into County Tax Collector for tax bills and liens. |
| **`/title <query>`** | `/title 1883 Cedar Dr` | 5-Pillar Title Confluence Screen (A-F Grade + 1980 Cutoff). |
| **`/otc [county]`** | `/otc Kent` | Summarizes Over-The-Counter (OTC) tax liens across Maryland. |
| **`/gradea`** | `/gradea` | Lists the top Grade A (Low-Risk) OTC Tax Lien Deals. |
| **`/deals [county]`** | `/deals Wicomico` | Filters Grade A & B OTC deals for a specific county. |
| **`/sync`** | `/sync` | Crawls Maryland county websites for the newest OTC lists & imports them. |
| **`/import <url> [county]`** | `/import https://.../otc.pdf` | Downloads and imports an OTC list directly from a URL. |
| **`Upload File (.csv/.xlsx/.pdf)`** | *(Attach file in Telegram)* | Automatically parses, standardizes, grades, and merges into the live database. |
| **`/offer <query>`** | `/offer 1883 Cedar Dr` | Calculates 3 strategic investor offer tiers based on recorded deed basis. |
| **`/save <query>`** | `/save 1883 Cedar Dr` | Saves markdown dossier to Obsidian Wiki and updates master index. |

---

## 🚀 Execution & Cloud Deployment

* **Live Web Platform + Embedded Telegram Bot + 12h Auto-Sync Daemon:**
  ```cmd
  "C:\Users\Owner\AppData\Local\Programs\Python\Python312\python.exe" c:\Obsedian\RealEstateResearch\RealEstateResearch\app.py
  ```
* **Cloud Deployment (Render Free Tier + GitHub 24/7):**
  Configured with root `render.yaml`, `.github/workflows/keep_alive.yml`, `Procfile`, and `requirements.txt` (`python RealEstateResearch/app.py`), plus an embedded `RENDER_EXTERNAL_URL` 10-minute self-ping worker.
* **Cloud Deployment (Railway):**
  Configured with root `Procfile`, `requirements.txt`, and `railway.json` (`web: python RealEstateResearch/app.py`).
* **Console Bot-Only Startup:**
  ```cmd
  c:\Obsedian\RealEstateResearch\RealEstateResearch\start_real_estate_bot.bat
  ```
* **Silent Background Execution:**
  ```cmd
  wscript.exe c:\Obsedian\RealEstateResearch\RealEstateResearch\start_real_estate_bot_silent.vbs
  ```

---

## 🔗 Related Knowledge Base Links
* [[Analysis - 1883 Cedar Drive Severn MD]]
* [[Accessing County Parcel Databases and GIS Data]]
* [[Maryland Tax Lien Investing]]
* [[Maryland Tax Sale Due Diligence and Parcel Screening]]
* [[Property Due Diligence Funnel]]
