"""
Illinois 31-County Live Parcel & Tax Lien Intelligence Engine
=============================================================
Provides dynamic, zero-login live parcel lookups across 31 priority Illinois
counties (22 counties with direct live ArcGIS REST / Socrata Open Data APIs +
9 counties with instant PIN parsing, official Assessor/Treasurer/DevNet Wedge
deep-links, and automatic local tax-sale export indexing).

Statutory Framework: Illinois Property Tax Code (35 ILCS 200)
- Penalty Bid Cap (35 ILCS 200/21-215, P.A. 103-0555, eff. Jan 1, 2024):
  9% per 6-month period (18%/yr max bid-down; historically 18%/6mo = 36%/yr pre-2024).
- Subsequent Taxes (35 ILCS 200/21-355): 12% flat per year.
- Redemption Windows (35 ILCS 200/21-350):
  2.5 yrs (1-6 unit residential) | 2 yrs (vacant / other) | 6 mos (commercial/vacant 2+ yrs delinq.).
- Assessment Ratio (35 ILCS 200/9-145):
  33.33% of Fair Cash Value downstate (FMV ~= Assessed * 3);
  Cook County uses 10% (Class 2 Residential) / 25% (Class 5 Commercial/Industrial).
"""

import os
import re
import html
import json
import math
import glob
import urllib.parse
import concurrent.futures
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "raw")
SCRATCH_DIR = os.path.join(BASE_DIR, "scratch")
PUBLIC_BASE_URL = (
    os.environ.get("RENDER_EXTERNAL_URL")
    or os.environ.get("PUBLIC_URL")
    or "https://maryland-tax-lien-otc-platform.onrender.com"
).strip().rstrip("/")

CURRENT_TAX_YEAR = datetime.now().year - 1  # Illinois bills taxes 1 year in arrears

# ==================== 31 PRIORITY ILLINOIS COUNTIES REGISTRY ====================
IL_COUNTIES_31: Dict[str, Dict[str, Any]] = {
    "adams": {
        "name": "Adams",
        "region": "Western IL (Quincy)",
        "pin_digits": 12,
        "pin_example": "01-00-001-000-00",
        "api_type": "arcgis",
        "arcgis_url": "https://services3.arcgis.com/BXTAaNPMn1VANOeH/arcgis/rest/services/ParcelsOnlineMap/FeatureServer/0",
        "pin_fields": ["PIN"],
        "addr_fields": ["SiteAddress"],
        "owner_fields": ["OwnerName"],
        "field_map": {
            "pin": ["PIN"],
            "owner": ["OwnerName"],
            "situs": ["SiteAddress"],
            "mail_addr": ["OwnerAddress", "OwnerAddress2"],
            "mail_csz": ["OwnerCSZ"],
            "acres": ["Acres"],
            "legal": ["LegalDesc"],
            "township": ["Township"],
            "tax_code": ["TaxCode"],
            "prop_class": ["UseCode"],
            "assessed_val": ["TotalValue"],
            "tax_billed": ["TaxDue"],
            "doc_num": ["DocNumber"],
            "weblink": ["Weblink"],
        },
        "devnet_slug": "adams",
        "assessor_url": "https://adamsil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.adamscountyil.gov/government/departments/treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/adams-county/",
    },
    "boone": {
        "name": "Boone",
        "region": "Northern IL (Belvidere)",
        "pin_digits": 10,
        "pin_example": "07-31-400-006",
        "api_type": "arcgis",
        "arcgis_url": "https://maps.boonecountyil.org/arcgis/rest/services/Assessment_Parcels/MapServer/0",
        "pin_fields": ["pin", "PWD"],
        "addr_fields": ["site_add"],
        "owner_fields": [],
        "field_map": {
            "pin": ["PWD", "pin"],
            "situs": ["site_add"],
            "situs_city": ["site_city"],
            "situs_state": ["site_state"],
            "situs_zip": ["site_zip"],
            "acres": ["acres"],
            "legal": ["legal"],
            "township": ["township_name", "township"],
        },
        "devnet_slug": "boone",
        "assessor_url": "https://booneil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.boonecountyil.gov/departments/treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/boone-county/",
    },
    "champaign": {
        "name": "Champaign",
        "region": "East-Central IL (Champaign-Urbana)",
        "pin_digits": 12,
        "pin_example": "46-21-07-302-014",
        "api_type": "portal",
        "devnet_slug": "champaign",
        "assessor_url": "https://champaignil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.champaigncountyil.gov/treasurer/tax-sale",
        "gis_url": "https://maps.ccgisc.org/public/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/champaign-county/",
    },
    "cook": {
        "name": "Cook",
        "region": "Chicagoland (Chicago & Suburbs)",
        "pin_digits": 14,
        "pin_example": "33-31-402-022-0000",
        "api_type": "cook_socrata",
        "arcgis_url": "https://gis.cookcountyil.gov/traditional/rest/services/parcelHistorical/MapServer/2025",
        "assessor_url": "https://www.cookcountyassessor.com/pin/{pin_digits}",
        "treasurer_url": "https://www.cookcountypropertyinfo.com/pinresults.aspx?pin={pin_digits}",
        "tax_sale_url": "https://www.cookcountytreasurer.com/setsearchparameters.aspx",
        "gis_url": "https://maps.cookcountyil.gov/cookviewer/",
        "trustee_url": "https://www.cookcountytreasurer.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/cook-county/",
    },
    "dekalb": {
        "name": "DeKalb",
        "region": "Northern IL (DeKalb / Sycamore)",
        "pin_digits": 10,
        "pin_example": "01-01-100-001",
        "api_type": "arcgis",
        "arcgis_url": "https://services7.arcgis.com/hEXJrPwm89CLXBYe/arcgis/rest/services/DeKalbIL_Parcels/FeatureServer/0",
        "pin_fields": ["Parcel_Number"],
        "addr_fields": ["SiteAddress"],
        "owner_fields": ["Owner"],
        "field_map": {
            "pin": ["Parcel_Number"],
            "owner": ["Owner", "TaxBillMailedTo"],
            "situs": ["SiteAddress"],
            "mail_addr": ["MailingAddress"],
            "acres": ["gross_current_acres"],
            "tax_code": ["tax_code"],
            "assessed_val": ["net_taxable_value"],
            "tax_billed": ["tax_billed"],
            "tax_rate": ["tax_rate"],
            "zoning": ["Zone_Code", "Special_Use"],
            "weblink": ["Compass_hyperlink", "QTAS_Link"],
        },
        "devnet_slug": "dekalb",
        "assessor_url": "https://dekalbil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://dekalbcounty.org/departments/treasurer/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/dekalb-county/",
    },
    "dupage": {
        "name": "DuPage",
        "region": "Chicagoland Collar (Wheaton / Naperville)",
        "pin_digits": 10,
        "pin_example": "06-15-117-021",
        "api_type": "arcgis",
        "arcgis_url": "https://gis.dupageco.org/arcgis/rest/services/DuPage_County_IL/ParcelsWithRealEstateCC/FeatureServer/0",
        "pin_fields": ["PIN"],
        "addr_fields": ["PROPADDRL1", "PROPSTNAME"],
        "owner_fields": ["PROPNAME", "BILLNAME"],
        "field_map": {
            "pin": ["PIN"],
            "owner": ["PROPNAME", "BILLNAME"],
            "situs": ["PROPADDRL1"],
            "situs_city": ["PROPCITY"],
            "situs_state": ["PROPSTATE"],
            "situs_zip": ["PROPZIP"],
            "mail_addr": ["BILLADDRL1", "BILLADDRL2"],
            "mail_city": ["BILLCITY"],
            "mail_state": ["BILLSTATE"],
            "mail_zip": ["BILLZIP"],
            "acres": ["ACREAGE"],
            "legal_parts": ["LEGALDES1", "LEGALDES2", "LEGALDES3"],
            "municipality": ["MUNICIPALITY"],
            "tax_code": ["TAXCODE"],
            "prop_class": ["GIS_Prop_Class", "REA017_PROP_CLASS"],
            "land_val_parts": ["REA017_FCV_LAND"],
            "imp_val_parts": ["REA017_FCV_IMP"],
            "assessed_val": ["REA017_FCV_TOTAL", "BILLVALUE"],
            "tax_billed": ["TAXAMOUNT"],
            "tax_rate": ["TAXRATE"],
            "tax_status": ["PARCELSTAT"],
        },
        "assessor_url": "https://www.dupagecounty.gov/propertylookup/?pin={pin_digits}",
        "treasurer_url": "https://www.dupagecounty.gov/government/county_offices/treasurer/",
        "gis_url": "https://gis.dupageco.org/ParcelViewer/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/dupage-county/",
    },
    "grundy": {
        "name": "Grundy",
        "region": "Chicagoland Outer Collar (Morris)",
        "pin_digits": 10,
        "pin_example": "01-01-100-001",
        "api_type": "arcgis",
        "arcgis_url": "https://maps.grundyco.org/arcgis/rest/services/AssessmentDepartment/CountyParcelsTotalValue_SPIE/MapServer/0",
        "pin_fields": ["Name", "PIN"],
        "addr_fields": ["PhysicalAddress1"],
        "owner_fields": ["TaxName"],
        "field_map": {
            "pin": ["PIN", "Name"],
            "owner": ["TaxName"],
            "situs": ["PhysicalAddress1", "PhysicalAddress2"],
            "situs_city": ["PhysicalCity"],
            "situs_state": ["PhysicalState"],
            "situs_zip": ["PhysicalZip"],
            "mail_addr": ["TaxAddress1", "TaxAddress2"],
            "mail_city": ["TaxCity"],
            "mail_state": ["TaxState"],
            "mail_zip": ["TaxZip"],
            "acres": ["LotAcres", "StatedArea"],
            "township": ["township"],
            "tax_code": ["TaxCode"],
            "prop_class": ["PropClass", "PropertyClassCode"],
            "land_val_parts": ["CurrentYearFLandVal", "CurrentYearNonFLandVal"],
            "imp_val_parts": ["CurrentYearFBldgVal", "CurrentYearNonFBldgVal"],
            "assessed_val": ["CurrentYearTotalVal"],
            "assess_year": ["AssessYear"],
        },
        "devnet_slug": "grundy",
        "assessor_url": "https://grundyil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.grundycountyil.gov/treasurer/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/grundy-county/",
    },
    "henry": {
        "name": "Henry",
        "region": "Quad Cities / Northwestern IL (Cambridge)",
        "pin_digits": 10,
        "pin_example": "24-28-427-010",
        "api_type": "arcgis",
        "arcgis_url": "https://services.arcgis.com/4YineAQdtmx0tv46/arcgis/rest/services/Parcel_Henry/FeatureServer/0",
        "pin_fields": ["PIN", "ParcelNumber_Formatted"],
        "addr_fields": ["location_addr", "Address"],
        "owner_fields": ["owner_name"],
        "field_map": {
            "pin": ["ParcelNumber_Formatted", "PIN"],
            "owner": ["owner_name"],
            "situs": ["location_addr", "Address"],
            "mail_addr": ["owner_address1", "owner_address2"],
            "mail_city": ["owner_city"],
            "mail_state": ["owner_state_code"],
            "mail_zip": ["owner_zip_code"],
            "acres": ["gross_acres", "ACREAGE"],
            "legal": ["short_legal"],
            "township": ["township"],
            "tax_code": ["tax_code"],
            "prop_class": ["use_code"],
            "land_val_parts": ["ag_land", "non_ag_land"],
            "imp_val_parts": ["ag_impr", "non_ag_impr"],
            "assessed_val": ["tot_assess", "taxable_eav"],
            "tax_billed": ["taxes_billed"],
            "assess_year": ["parcel_year"],
        },
        "devnet_slug": "henry",
        "assessor_url": "https://henryil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.henrycty.com/195/Treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/henry-county/",
    },
    "jackson": {
        "name": "Jackson",
        "region": "Southern IL (Carbondale / Murphysboro)",
        "pin_digits": 10,
        "pin_example": "15-21-201-001",
        "api_type": "portal",
        "devnet_slug": "jackson",
        "assessor_url": "https://jacksonil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.jacksoncounty-il.gov/government/departments-l-z/treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/jackson-county/",
    },
    "kane": {
        "name": "Kane",
        "region": "Chicagoland Collar (Aurora / Elgin / Geneva)",
        "pin_digits": 10,
        "pin_example": "01-01-100-001",
        "api_type": "arcgis",
        "arcgis_url": "https://services1.arcgis.com/oRKmdBXD6EbdmVgJ/arcgis/rest/services/KaneCo_IL_Parcels/FeatureServer/0",
        "pin_fields": ["PIN"],
        "addr_fields": ["SiteAddress"],
        "owner_fields": ["TaxName"],
        "field_map": {
            "pin": ["PIN"],
            "owner": ["TaxName"],
            "situs": ["SiteAddress"],
            "situs_city": ["SiteCity"],
            "situs_state": ["SiteState"],
            "situs_zip": ["SiteZip"],
            "mail_addr": ["MailingAddress", "MailingAddress2"],
            "mail_city": ["MailingCity"],
            "mail_state": ["MailingState"],
            "mail_zip": ["MailingZip"],
            "acres": ["RecordedAcreage"],
            "legal": ["LegalDesc"],
            "township": ["Township"],
            "municipality": ["Municipality"],
            "tax_code": ["TaxCode"],
            "prop_class": ["UseCodeDescription", "UseCode"],
            "doc_num": ["DocNumber"],
            "sale_date": ["DocDate"],
        },
        "devnet_slug": "kane",
        "assessor_url": "https://kaneil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.kanecountytreasurer.org/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/kane-county/",
    },
    "kankakee": {
        "name": "Kankakee",
        "region": "South Chicagoland (Kankakee / Bourbonnais)",
        "pin_digits": 12,
        "pin_example": "16-09-32-301-001",
        "api_type": "portal",
        "devnet_slug": "kankakee",
        "assessor_url": "https://kankakeeil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.k3county.net/treasurer",
        "gis_url": "https://k3gis.com/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/kankakee/",
    },
    "kendall": {
        "name": "Kendall",
        "region": "Chicagoland Collar (Yorkville / Oswego)",
        "pin_digits": 10,
        "pin_example": "01-06-100-006",
        "api_type": "arcgis",
        "arcgis_url": "https://maps.co.kendall.il.us/server/rest/services/Hosted/Parcels___Tax_District_Join/FeatureServer/0",
        "pin_fields": ["pin_dashless", "pin"],
        "addr_fields": [],
        "owner_fields": [],
        "field_map": {
            "pin": ["pin", "pin_dashless"],
            "township": ["township_1621436861456"],
            "municipality": ["municipality_1621436861456"],
            "tax_code": ["tax_code_1621436861456"],
            "school": ["unit_school", "high_school", "grade_school"],
        },
        "devnet_slug": "kendall",
        "assessor_url": "https://kendallil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.kendallcountyil.gov/offices/treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/kendall-county/",
    },
    "knox": {
        "name": "Knox",
        "region": "Western IL (Galesburg)",
        "pin_digits": 10,
        "pin_example": "99-10-301-001",
        "api_type": "portal",
        "devnet_slug": "knox",
        "assessor_url": "https://knoxil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.co.knox.il.us/treasurer/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/knox-county/",
    },
    "lake": {
        "name": "Lake",
        "region": "Chicagoland North Collar (Waukegan / Libertyville)",
        "pin_digits": 10,
        "pin_example": "01-12-301-005",
        "api_type": "arcgis",
        "arcgis_url": "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services/OpenData_ParcelPolygons/FeatureServer/0",
        "pin_fields": ["PIN"],
        "addr_fields": ["situs_addr_line_1_First"],
        "owner_fields": ["taxpayer_name"],
        "field_map": {
            "pin": ["PIN"],
            "owner": ["taxpayer_name"],
            "situs": ["situs_addr_line_1_First", "situs_addr_line_2_First"],
            "situs_city": ["situs_addr_city_First"],
            "situs_state": ["situs_addr_state_legdat_First"],
            "situs_zip": ["situs_addr_zip_legdat_First"],
            "mail_addr": ["taxpayer_addr_line_1", "taxpayer_addr_line_2"],
            "mail_city": ["taxpayer_addr_city"],
            "mail_state": ["taxpayer_addr_state"],
            "mail_zip": ["taxpayer_addr_zip"],
            "legal_parts": ["legdesc1", "legdesc2", "legdesc3"],
        },
        "assessor_url": "https://tax.lakecountyil.gov/datalets/datalet.aspx?mode=profileall&UseSearch=no&pin={pin_digits}",
        "treasurer_url": "https://www.lakecountyil.gov/361/Tax-Sale-Information",
        "gis_url": "https://maps.lakecountyil.gov/mapsonline/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/lake-county/",
    },
    "lasalle": {
        "name": "LaSalle",
        "region": "North-Central IL (Ottawa / LaSalle-Peru)",
        "pin_digits": 10,
        "pin_example": "33-36-109-025",
        "api_type": "arcgis",
        "arcgis_url": "https://gis.lasallecounty.org/arcgis/rest/services/LandValuesV2/MapServer/0",
        "pin_fields": ["PIN", "AssesosorPIN", "OLDPIN"],
        "addr_fields": ["SiteAddress", "PhysicalADDRESS1"],
        "owner_fields": ["TAXNAME"],
        "field_map": {
            "pin": ["PIN"],
            "owner": ["TAXNAME"],
            "situs": ["SiteAddress", "PhysicalADDRESS1"],
            "situs_city": ["PhysicalCITY"],
            "situs_state": ["PhysicalSTATE"],
            "situs_zip": ["PhysicalZIP"],
            "mail_addr": ["TaxADDRESS1", "TaxADDRESS2"],
            "mail_city": ["TaxCITY"],
            "mail_state": ["TaxSTATE"],
            "mail_zip": ["TaxZIP"],
            "acres": ["LOTACRES"],
            "legal": ["LEGAL"],
            "township": ["TOWNSHIP"],
            "tax_code": ["TAXCODE"],
            "prop_class": ["PROPCLASS", "TypeofUse"],
            "land_val_parts": ["CurrentYearFLandVal", "CurrentYearNonFLandVal"],
            "imp_val_parts": ["CurrentYearFBldgVal", "CurrentYearNonFBldgVal"],
            "assessed_val": ["CurrentYearTotalVal"],
            "assess_year": ["ASSESSYEAR"],
            "sale_price": ["SALEPRICE"],
            "sale_date": ["SALEDATE"],
            "year_built": ["YearBuilt"],
            "bldg_sqft": ["TotalBuildingSQFT"],
        },
        "assessor_url": "https://lasallecountyil.gov/249/Supervisor-of-Assessments",
        "treasurer_url": "https://lasallecountyil.gov/252/Treasurer",
        "gis_url": "https://gis.lasallecounty.org/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/lasalle/",
    },
    "macon": {
        "name": "Macon",
        "region": "Central IL (Decatur)",
        "pin_digits": 12,
        "pin_example": "04-12-23-230-040",
        "api_type": "arcgis",
        "arcgis_url": "https://services1.arcgis.com/a3k0qIja5SolIRYR/arcgis/rest/services/SRS2026Parcels/FeatureServer/0",
        "pin_fields": ["ParcelNumb", "Name", "AlternateP"],
        "addr_fields": ["SiteAddres"],
        "owner_fields": ["PrimaryNam"],
        "field_map": {
            "pin": ["ParcelNumb", "Name"],
            "owner": ["PrimaryNam"],
            "situs": ["SiteAddres"],
            "mail_addr": ["PrimaryAdd"],
            "acres": ["Acres", "Acreage"],
            "legal": ["LegalDescr"],
            "subdivision": ["Subdivisio"],
            "township": ["TownshipNa"],
            "tax_code": ["TaxCode"],
            "prop_class": ["Use_", "UseCode"],
            "zoning": ["Zoning"],
            "land_val_parts": ["LandLot", "FarmLand"],
            "imp_val_parts": ["Buildings", "FarmBlding"],
            "assessed_val": ["Total"],
            "sale_price": ["Price"],
            "sale_date": ["SaleDate"],
            "bldg_sqft": ["SqFt"],
            "doc_num": ["Doc"],
        },
        "assessor_url": "https://www.maconcounty.illinois.gov/offices/supervisor-of-assessments/",
        "treasurer_url": "https://www.maconcounty.illinois.gov/offices/treasurer/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/macon-county/",
    },
    "madison": {
        "name": "Madison",
        "region": "Metro East St. Louis (Edwardsville / Alton)",
        "pin_digits": 15,
        "pin_example": "07-1-11-02-00-000-002",
        "api_type": "arcgis",
        "arcgis_url": "https://services.arcgis.com/Z0kKj2K728ngqqrp/arcgis/rest/services/County_Parcels/FeatureServer/12",
        "pin_fields": ["PIN", "CO_PIN"],
        "addr_fields": ["ST_NAME"],
        "owner_fields": ["OWN_FULL", "OWN_LAST"],
        "field_map": {
            "pin": ["PIN", "CO_PIN"],
            "owner": ["OWN_FULL"],
            "situs_parts": ["NUM", "ST_PRE", "ST_NAME", "ST_TYPE", "ST_POST"],
            "situs_city": ["CITY"],
            "situs_state": ["STATE"],
            "situs_zip": ["ZIP"],
            "mail_addr": ["OWN_ADD", "OWN_ADD_2"],
            "mail_city": ["OWN_CITY"],
            "mail_state": ["OWN_STATE"],
            "mail_zip": ["OWN_ZIP"],
            "acres": ["ACRES"],
            "sqft": ["SQFT"],
            "municipality": ["COMM"],
        },
        "devnet_slug": "madison",
        "assessor_url": "https://madisonil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.madisoncountyil.gov/departments/treasurer/tax_sale_information.php",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/madison-county/",
    },
    "mchenry": {
        "name": "McHenry",
        "region": "Chicagoland NW Collar (Woodstock / Crystal Lake)",
        "pin_digits": 10,
        "pin_example": "01-01-301-003",
        "api_type": "arcgis",
        "arcgis_url": "https://services5.arcgis.com/72ZZon8FQb6nYtKt/arcgis/rest/services/Parcels/FeatureServer/0",
        "pin_fields": ["parcel_number"],
        "addr_fields": ["Address"],
        "owner_fields": [],
        "field_map": {
            "pin": ["parcel_number"],
            "situs": ["Address"],
            "tax_code": ["py_tax_code"],
            "prop_class": ["use_code_group", "land_use"],
            "tax_status": ["tax_status"],
            "assess_year": ["parcel_year"],
        },
        "devnet_slug": "mchenry",
        "assessor_url": "https://mchenryil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.mchenrycountyil.gov/departments/treasurer/tax-sale",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/mchenry-county/",
    },
    "mclean": {
        "name": "McLean",
        "region": "Central IL (Bloomington-Normal)",
        "pin_digits": 10,
        "pin_example": "14-25-277-020",
        "api_type": "arcgis",
        "arcgis_url": "https://www.mcgisweb.org/mcgc/rest/services/Cadastral/Cadastral_Web/MapServer/0",
        "pin_fields": ["PIN", "Dash_PIN"],
        "addr_fields": ["address1"],
        "owner_fields": ["last_name"],
        "field_map": {
            "pin": ["Dash_PIN", "PIN"],
            "owner_parts": ["first_name", "middle_initial", "last_name"],
            "situs": ["address1", "address2"],
            "situs_city": ["city"],
            "situs_state": ["state_code"],
            "situs_zip": ["zip_code"],
            "acres": ["COMPUTED_AC", "DEED_AC"],
            "township": ["TWNSHPLAB"],
            "assess_year": ["parcel_year"],
            "weblink": ["Assessor", "Tax"],
        },
        "devnet_slug": "mclean",
        "assessor_url": "https://mcleanil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.mcleancountyil.gov/117/Treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/mclean-county/",
    },
    "ogle": {
        "name": "Ogle",
        "region": "Northern IL (Oregon / Rochelle)",
        "pin_digits": 10,
        "pin_example": "16-03-401-001",
        "api_type": "portal",
        "devnet_slug": "ogle",
        "assessor_url": "https://ogleil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.oglecountyil.gov/departments/treasurer/index.php",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/ogle-county/",
    },
    "peoria": {
        "name": "Peoria",
        "region": "Central IL (Peoria Metro)",
        "pin_digits": 10,
        "pin_example": "17-26-329-017",
        "api_type": "arcgis",
        "arcgis_url": "https://services.arcgis.com/iPiPjILCMYxPZWTc/arcgis/rest/services/Tax_Parcels/FeatureServer/5",
        "pin_fields": ["PIN"],
        "addr_fields": ["prop_street", "COMBADD"],
        "owner_fields": ["owner_name", "LAST"],
        "field_map": {
            "pin": ["PIN"],
            "owner": ["owner_name"],
            "situs": ["prop_street", "COMBADD"],
            "situs_city": ["CITY"],
            "situs_state": ["STATE"],
            "situs_zip": ["PZIP"],
            "mail_addr": ["ADDR1", "ADDR2"],
            "mail_city": ["OWNCTY"],
            "mail_state": ["OWNSTE"],
            "mail_zip": ["OWZIP"],
            "acres": ["Acres"],
            "legal": ["LEGAL"],
            "tax_code": ["TAX_"],
            "prop_class": ["PropClass", "mkt_house_type"],
            "land_val_parts": ["land_lot_value", "farm_lot_value"],
            "imp_val_parts": ["improvements_value", "farm_building_value"],
            "assessed_val": ["total_assessed_value"],
            "year_built": ["year_built"],
            "bldg_sqft": ["total_living_area", "main_living_area"],
            "beds": ["n_bedrooms"],
            "baths": ["full_baths"],
        },
        "assessor_url": "https://www.peoriacounty.gov/386/Property-Tax-Inquiry",
        "treasurer_url": "https://www.peoriacounty.gov/376/Treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/peoria-county/",
    },
    "rockisland": {
        "name": "Rock Island",
        "region": "Quad Cities (Rock Island / Moline)",
        "pin_digits": 10,
        "pin_example": "01-33-300-004",
        "api_type": "arcgis",
        "arcgis_url": "https://services9.arcgis.com/6FnscPPlUa9DXXOk/arcgis/rest/services/Parcels/FeatureServer/0",
        "pin_fields": ["PIN", "parcel_number"],
        "addr_fields": ["site_address"],
        "owner_fields": ["owner1_name", "taxbill_name"],
        "field_map": {
            "pin": ["PIN", "parcel_number"],
            "owner": ["owner1_name", "taxbill_name"],
            "situs": ["site_address"],
            "situs_city": ["Site_City"],
            "situs_state": ["Site_State"],
            "situs_zip": ["Site_Zip"],
            "mail_addr": ["owner1_address1", "taxbill_addr1"],
            "mail_csz": ["owner1_csz", "taxbill_csz"],
            "acres": ["gross_acres", "GIS_acres_num"],
            "legal": ["legal"],
            "township": ["township"],
            "municipality": ["municipality"],
            "tax_code": ["tax_code"],
            "prop_class": ["class"],
            "zoning": ["Zoning"],
            "flood": ["FLOOD"],
            "total_fcv": ["EMV"],
            "assessed_val": ["EAV"],
            "land_val_parts": ["farm_land", "non_farm_land"],
            "imp_val_parts": ["farm_building", "non_farm_building"],
            "sale_price": ["gross_sale_price", "net_sale_price"],
            "sale_date": ["date_last_sale", "date_of_sale"],
            "year_built": ["YRBuilt"],
            "bldg_sqft": ["TOTSQFT"],
            "lat": ["Y_latitude"],
            "lon": ["X_longitude"],
        },
        "devnet_slug": "rockisland",
        "assessor_url": "https://rockislandil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.rockislandcountyil.gov/252/Treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/rock-island-county/",
    },
    "sangamon": {
        "name": "Sangamon",
        "region": "Central IL (Springfield State Capital)",
        "pin_digits": 11,
        "pin_example": "14-28.0-401-012",
        "api_type": "portal",
        "assessor_url": "https://tax.co.sangamon.il.us/",
        "treasurer_url": "https://sangamonil.gov/departments/s-z/treasurer",
        "gis_url": "https://www.sangis.org/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/sangamon-county/",
    },
    "stclair": {
        "name": "St. Clair",
        "region": "Metro East St. Louis (Belleville / O'Fallon)",
        "pin_digits": 11,
        "pin_example": "21-35.0-300-010",
        "api_type": "arcgis",
        "arcgis_url": "https://arcgispublicmap.co.st-clair.il.us/server/rest/services/SCC_parcel_map_data/MapServer/29",
        "pin_fields": ["parcel_number", "parcelid"],
        "addr_fields": ["siteadr1", "sitename"],
        "owner_fields": ["owner"],
        "field_map": {
            "pin": ["parcelid", "parcel_number"],
            "owner": ["owner"],
            "situs": ["siteadr1"],
            "situs_city": ["sitecity"],
            "situs_state": ["sitest"],
            "situs_zip": ["sitezip"],
            "mail_addr": ["address", "address2"],
            "mail_csz": ["cityst"],
            "mail_zip": ["zipcode"],
            "acres": ["totacre", "acreage"],
            "legal_parts": ["legal1", "legal2", "legal3", "legal4"],
            "subdivision": ["subdiv"],
            "township": ["twpname"],
            "tax_code": ["tcacode"],
            "prop_class": ["landuse", "class"],
            "land_val_parts": ["landval", "farmland", "farmhome"],
            "imp_val_parts": ["bldgval", "farmdwel", "farmbldg"],
            "assessed_val": ["totamt"],
            "assess_year": ["paryear"],
            "doc_num": ["document_number1"],
            "tax_status": ["status"],
        },
        "devnet_slug": "stclair",
        "assessor_url": "https://stclairil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.co.st-clair.il.us/departments/treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/st-clair-county/",
    },
    "tazewell": {
        "name": "Tazewell",
        "region": "Central IL (Pekin / East Peoria)",
        "pin_digits": 12,
        "pin_example": "23-23-22-307-010",
        "api_type": "arcgis",
        "arcgis_url": "https://gis.tazewell-il.gov/arcgis/rest/services/WAB/TazCo_Parcels_WithOwner/MapServer/1",
        "pin_fields": ["parcel_number", "PIN2", "PIN"],
        "addr_fields": ["site_address"],
        "owner_fields": ["owner1_name", "taxbill_name"],
        "field_map": {
            "pin": ["PIN", "parcel_number"],
            "owner": ["owner1_name", "taxbill_name"],
            "situs": ["site_address"],
            "situs_csz": ["site_csz"],
            "mail_addr": ["owner1_address1", "owner1_address2", "mailto_address1"],
            "mail_csz": ["owner1_csz", "mailto_csz"],
            "acres": ["gross_acres", "homesite_acres", "farm_acres"],
            "legal": ["legal"],
            "township": ["township_name"],
            "tax_code": ["tax_code"],
            "prop_class": ["class", "current_assess_category"],
            "land_val_parts": ["non_farm_land", "farm_land"],
            "imp_val_parts": ["non_farm_building", "farm_building"],
            "assessed_val": [],
            "tax_billed": ["tax_billed", "taxbill_tax"],
            "tax_rate": ["taxbill_rate"],
            "tax_status": ["tax_status"],
            "sale_price": ["gross_sale_price", "net_sale_price"],
            "sale_date": ["date_last_sale", "date_of_sale"],
            "doc_num": ["document_no1"],
            "install1_paid": ["install_1_paid_date"],
            "install2_paid": ["install_2_paid_date"],
        },
        "devnet_slug": "tazewell",
        "assessor_url": "https://tazewellil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.tazewell-il.gov/191/Treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/tazewell-county/",
    },
    "vermilion": {
        "name": "Vermilion",
        "region": "East-Central IL (Danville)",
        "pin_digits": 10,
        "pin_example": "13-33-100-004",
        "api_type": "arcgis",
        "arcgis_url": "https://gis.cityofdanville.org/arcgis/rest/services/Hosted/Tax_Parcels_Public/FeatureServer/0",
        "pin_fields": ["parcel_id", "pin_raw"],
        "addr_fields": ["site_address"],
        "owner_fields": ["owner_name"],
        "field_map": {
            "pin": ["parcel_id", "pin_raw"],
            "owner": ["owner_name"],
            "situs": ["site_address"],
            "situs_city": ["site_city"],
            "situs_state": ["site_state"],
            "situs_zip": ["site_zip"],
            "mail_addr": ["owner_address"],
            "mail_city": ["owner_city"],
            "mail_state": ["owner_state"],
            "mail_zip": ["owner_zip"],
            "acres": ["gross_acres"],
            "legal": ["legal_description"],
            "prop_class": ["class_code"],
            "weblink": ["tax_card"],
        },
        "devnet_slug": "vermilion",
        "assessor_url": "https://vermilionil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.vercounty.org/treasurer/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/vermillion-county/",
    },
    "white": {
        "name": "White",
        "region": "Southeastern IL (Carmi)",
        "pin_digits": 10,
        "pin_example": "13-13-101-001",
        "api_type": "portal",
        "devnet_slug": "white",
        "assessor_url": "https://whiteil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.whitecounty-il.gov/treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/white-county/",
    },
    "whiteside": {
        "name": "Whiteside",
        "region": "Northwestern IL (Sterling / Rock Falls / Morrison)",
        "pin_digits": 10,
        "pin_example": "22-36-400-002",
        "api_type": "arcgis",
        "arcgis_url": "https://services.arcgis.com/l0M0OC6J9QAHCiGx/arcgis/rest/services/Tax_Parcels_Ver_2_Parcels_Only/FeatureServer/0",
        "pin_fields": ["PARCELID", "LOWPARCELID"],
        "addr_fields": ["SITEADDRESS"],
        "owner_fields": ["OWNERNME1"],
        "field_map": {
            "pin": ["PARCELID", "LOWPARCELID"],
            "owner": ["OWNERNME1", "OWNERNME2"],
            "situs": ["SITEADDRESS", "SITEADDRESS2"],
            "mail_addr": ["PSTLADDRESS", "PSTLADDRESS2"],
            "mail_city": ["PSTLCITY"],
            "mail_state": ["PSTLSTATE"],
            "mail_zip": ["PSTLZIP5"],
            "acres": ["STATEDAREA"],
            "legal": ["PRPRTYDSCRP"],
            "tax_code": ["CVTTXCD"],
            "prop_class": ["CLASSDSCRP", "CLASSCD", "USEDSCRP"],
            "land_val_parts": ["LNDVALUE"],
            "assessed_val": ["CNTASSDVAL", "CNTTXBLVAL"],
            "tax_billed": ["TOTCNTTXOD", "TOTPRVTXTOD"],
            "year_built": ["RESYRBLT"],
            "bldg_sqft": ["RESFLRAREA", "BLDGAREA"],
            "doc_num": ["DOCNUM"],
            "weblink": ["WEDGEURL", "PRCURL"],
        },
        "devnet_slug": "whiteside",
        "assessor_url": "https://whitesideil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.whitesidecountyil.gov/196/Treasurer",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/whiteside-county/",
    },
    "will": {
        "name": "Will",
        "region": "Chicagoland South Collar (Joliet / Bolingbrook / Plainfield)",
        "pin_digits": 16,
        "pin_example": "19-09-14-205-002-0000",
        "api_type": "arcgis",
        "arcgis_url": "https://gis.willcountyillinois.com/hosting/rest/services/HistoricParcels/Parcels_2022/MapServer/0",
        "pin_fields": ["PIN", "ParcelID"],
        "addr_fields": [],
        "owner_fields": [],
        "field_map": {
            "pin": ["PIN", "ParcelID"],
        },
        "assessor_url": "https://willcountysoa.com/ParcelSearch",
        "treasurer_url": "https://www.willcountytreasurer.com/",
        "gis_url": "https://gis.willcountyillinois.com/gisweb/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/will-county/",
    },
    "williamson": {
        "name": "Williamson",
        "region": "Southern IL (Marion / Herrin)",
        "pin_digits": 10,
        "pin_example": "06-18-301-001",
        "api_type": "portal",
        "devnet_slug": "williamson",
        "assessor_url": "https://williamsonil.devnetwedge.com/parcel/view/{pin_digits}/{tax_year}",
        "treasurer_url": "https://www.williamsoncountyil.gov/treasurer/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/williamson/",
    },
    "winnebago": {
        "name": "Winnebago",
        "region": "Northern IL (Rockford)",
        "pin_digits": 10,
        "pin_example": "11-23-456-007",
        "api_type": "portal",
        "assessor_url": "https://tax.wincoil.gov/",
        "treasurer_url": "https://wincoil.gov/departments/treasurer",
        "gis_url": "https://maps.wingis.org/",
        "trustee_url": "https://iltaxsale.com/",
        "tls_url": "https://vault.taxlienschool.com/tax-lien/tax-lien-states/illinois-the-best-tax-lien-state-with-36percent-return-on-investment/winnebago-county/",
    },
}

# Canonical county name aliases for natural-language queries
IL_COUNTY_ALIASES: Dict[str, str] = {}
for _ck, _meta in IL_COUNTIES_31.items():
    IL_COUNTY_ALIASES[_ck] = _ck
    IL_COUNTY_ALIASES[_meta["name"].lower()] = _ck
    IL_COUNTY_ALIASES[_meta["name"].lower().replace(".", "").replace(" ", "")] = _ck
IL_COUNTY_ALIASES.update({
    "st. clair": "stclair",
    "st clair": "stclair",
    "saint clair": "stclair",
    "rock island": "rockisland",
    "la salle": "lasalle",
    "vermillion": "vermilion",
    "du page": "dupage",
    "de kalb": "dekalb",
    "mc henry": "mchenry",
    "mc lean": "mclean",
})

# High-priority 10-digit PIN live counties probed in parallel when no county name is specified
AUTO_FANOUT_10DIGIT = [
    "dupage", "lake", "kane", "peoria", "mclean", "rockisland",
    "dekalb", "grundy", "mchenry", "kendall", "lasalle", "henry",
    "boone", "whiteside", "vermilion",
]
AUTO_FANOUT_12DIGIT = ["tazewell", "macon", "adams"]


# ==================== HELPERS ====================
def normalize_il_county(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    clean = re.sub(r"\s+county$", "", str(name).strip().lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    if clean in IL_COUNTY_ALIASES:
        return IL_COUNTY_ALIASES[clean]
    compact = clean.replace(".", "").replace(" ", "").replace("-", "")
    return IL_COUNTY_ALIASES.get(compact)


def clean_pin_digits(pin_str: str) -> str:
    return re.sub(r"[^0-9]", "", str(pin_str or ""))


def format_il_pin(digits: str, county_key: Optional[str] = None) -> str:
    d = clean_pin_digits(digits)
    if county_key == "cook" or len(d) == 14:
        if len(d) == 14:
            return f"{d[0:2]}-{d[2:4]}-{d[4:7]}-{d[7:10]}-{d[10:14]}"
    if county_key == "will" or len(d) == 16:
        if len(d) == 16:
            return f"{d[0:2]}-{d[2:4]}-{d[4:6]}-{d[6:9]}-{d[9:12]}-{d[12:16]}"
    if county_key == "madison" or len(d) == 15:
        if len(d) == 15:
            return f"{d[0:2]}-{d[2]}-{d[3:5]}-{d[5:7]}-{d[7:9]}-{d[9:12]}-{d[12:15]}"
    if county_key in ("stclair", "sangamon") and len(d) == 11:
        return f"{d[0:2]}-{d[2:4]}.{d[4]}-{d[5:8]}-{d[8:11]}"
    if len(d) == 12:
        if county_key == "adams":
            return f"{d[0:2]}-{d[2:4]}-{d[4:7]}-{d[7:10]}-{d[10:12]}"
        return f"{d[0:2]}-{d[2:4]}-{d[4:6]}-{d[6:9]}-{d[9:12]}"
    if len(d) == 10:
        return f"{d[0:2]}-{d[2:4]}-{d[4:7]}-{d[7:10]}"
    return str(digits).strip()


def is_illinois_pin_pattern(query_str: str) -> bool:
    """Detect standardized Illinois Property Index Numbers (PINs)."""
    q = str(query_str or "").strip()
    patterns = [
        r"^\d{2}-\d{2}-\d{3}-\d{3}$",                       # 10-digit IL PIN (DuPage, Lake, Kane, Peoria, etc.)
        r"^\d{2}-\d{2}-\d{3}-\d{3}-\d{4}$",                 # 14-digit Cook County PIN
        r"^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}$",                 # 12-digit Tazewell / Macon / Champaign / Kankakee PIN
        r"^\d{2}-\d{2}-\d{3}-\d{3}-\d{2}$",                 # 12-digit Adams PIN
        r"^\d{2}-\d{1}-\d{4}-\d{3}-\d{2}$",                 # Adams alternate PIN
        r"^\d{2}-\d{2}\.\d-\d{3}-\d{3}$",                   # 11-digit dotted St. Clair / Sangamon PIN
        r"^\d{2}-\d{1}-\d{2}-\d{2}-\d{2}-\d{3}-\d{3}$",     # 15-digit Madison County PIN
        r"^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}-\d{4}$",           # 16-digit Will County PIN
    ]
    return any(re.match(p, q) for p in patterns)


def _safe_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    try:
        s = str(v).replace("$", "").replace(",", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _first_val(att: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = att.get(k)
        if v is not None and str(v).strip() not in ("", "None", "null", "0"):
            return str(v).strip()
    return ""


def _sum_vals(att: Dict[str, Any], keys: List[str]) -> float:
    return sum(_safe_float(att.get(k)) for k in keys)


def _centroid_from_geometry(geom: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    if not geom:
        return None, None
    if "x" in geom and "y" in geom:
        return round(float(geom["y"]), 6), round(float(geom["x"]), 6)
    rings = geom.get("rings")
    if rings and rings[0]:
        pts = rings[0]
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        if -95 <= lon <= -85 and 36 <= lat <= 43:
            return round(lat, 6), round(lon, 6)
    return None, None


def _cook_class_description(cls_code: str) -> Tuple[str, float]:
    """Return (description, assessment_ratio) for Cook County Assessor property class."""
    c = str(cls_code or "").strip().upper()
    if c.startswith("EX") or c == "0":
        return "Exempt / Government / Non-Taxable", 0.0
    if c.startswith("1"):
        return f"Vacant Land (Cook Class {c})", 0.10
    if c.startswith("2"):
        return f"Residential 1-6 Units (Cook Class {c})", 0.10
    if c.startswith("3"):
        return f"Multifamily / Apartment 7+ Units (Cook Class {c})", 0.10
    if c.startswith("4"):
        return f"Not-for-Profit (Cook Class {c})", 0.25
    if c.startswith("5"):
        return f"Commercial / Industrial (Cook Class {c})", 0.25
    if c.startswith("6") or c.startswith("7") or c.startswith("8"):
        return f"Incentive Commercial/Industrial (Cook Class {c})", 0.10
    return f"Cook Property Class {c or 'N/A'}", 0.10


def _build_county_links(county_key: str, pin_raw: str, weblink: str = "") -> Dict[str, str]:
    meta = IL_COUNTIES_31[county_key]
    digits = clean_pin_digits(pin_raw)
    pin_fmt = format_il_pin(digits, county_key) if digits else pin_raw
    assessor = weblink or meta.get("assessor_url", "").format(
        pin_digits=digits or pin_raw,
        pin_fmt=pin_fmt,
        tax_year=CURRENT_TAX_YEAR,
    )
    treasurer = meta.get("treasurer_url", "").format(
        pin_digits=digits or pin_raw,
        pin_fmt=pin_fmt,
        tax_year=CURRENT_TAX_YEAR,
    )
    q_web = urllib.parse.quote(f"{meta['name']} IL {pin_fmt or pin_raw}")
    dossier_url = f"{PUBLIC_BASE_URL}/parcel?q={q_web}"
    return {
        "assessor_link": assessor,
        "treasurer_link": treasurer,
        "trustee_link": meta.get("trustee_url", "https://iltaxsale.com/"),
        "gis_link": meta.get("gis_url", ""),
        "tls_link": meta.get("tls_url", ""),
        "dossier_url": dossier_url,
    }


# ==================== COOK COUNTY LIVE SOCRATA + GIS ENGINE ====================
def fetch_cook_county_live(query_str: str) -> List[Dict[str, Any]]:
    """
    Live 2026 Cook County parcel lookup via official Cook County Open Data Socrata APIs:
    - 3723-97qp: Assessor Parcel Addresses & Taxpayer Mailing
    - uzyt-m557: Assessor Assessed Values (Land / Bldg / Total)
    - nj4t-kc8j: Assessor Parcel Universe (Lat/Lon, Township, Tax Code, TIF)
    - x54s-btds: Residential Characteristics (YrBuilt, Bldg SqFt, Land SqFt, Beds/Baths)
    - wvhk-k5uv: Recorded Parcel Sales History
    """
    q = str(query_str or "").strip()
    digits = clean_pin_digits(q)
    headers = {"User-Agent": "IllinoisRealEstateBot/1.0"}
    pins_to_enrich: List[str] = []
    addr_records: Dict[str, Dict[str, Any]] = {}

    # 1. Resolve PIN(s) either directly from 10/14-digit PIN or by Street Address search
    if len(digits) == 14:
        pins_to_enrich = [digits]
    elif len(digits) == 10:
        pins_to_enrich = [digits + "0000"]
    else:
        # Address / Owner search via Cook Assessor Parcel Addresses (3723-97qp) using fast full-text $q index
        q_addr = re.sub(r"[^A-Z0-9\s]", "", q.upper()).strip()
        if len(q_addr) >= 4:
            for yr in (str(datetime.now().year), str(datetime.now().year - 1)):
                try:
                    r = requests.get(
                        "https://datacatalog.cookcountyil.gov/resource/3723-97qp.json",
                        params={"$q": q_addr, "year": yr, "$limit": 6},
                        timeout=8,
                        headers=headers,
                    )
                    if r.status_code == 200:
                        seen = set()
                        for row in r.json():
                            p = str(row.get("pin") or "")
                            if p and p not in seen:
                                seen.add(p)
                                pins_to_enrich.append(p)
                                addr_records[p] = row
                                if len(pins_to_enrich) >= 3:
                                    break
                    if pins_to_enrich:
                        break
                except Exception:
                    pass

    if not pins_to_enrich:
        return []

    results = []
    for pin14 in pins_to_enrich[:3]:
        endpoints = {
            "addr": ("https://datacatalog.cookcountyil.gov/resource/3723-97qp.json", {"pin": pin14, "$order": "year DESC", "$limit": 1}),
            "val": ("https://datacatalog.cookcountyil.gov/resource/uzyt-m557.json", {"pin": pin14, "$order": "year DESC", "$limit": 1}),
            "univ": ("https://datacatalog.cookcountyil.gov/resource/nj4t-kc8j.json", {"pin": pin14, "$order": "year DESC", "$limit": 1}),
            "chars": ("https://datacatalog.cookcountyil.gov/resource/x54s-btds.json", {"pin": pin14, "$order": "year DESC", "$limit": 1}),
            "sales": ("https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json", {"pin": pin14, "$order": "sale_date DESC", "$limit": 1}),
        }

        fetched: Dict[str, Dict[str, Any]] = {}
        if pin14 in addr_records:
            fetched["addr"] = addr_records[pin14]
            endpoints.pop("addr", None)

        def _get_one(item):
            key, (url, params) = item
            try:
                resp = requests.get(url, params=params, timeout=8, headers=headers)
                if resp.status_code == 200:
                    arr = resp.json()
                    if isinstance(arr, list) and arr:
                        return key, arr[0]
            except Exception:
                pass
            return key, {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            for k, row in ex.map(_get_one, endpoints.items()):
                if row:
                    fetched[k] = row

        if not any(fetched.values()):
            continue

        a = fetched.get("addr", {})
        v = fetched.get("val", {})
        u = fetched.get("univ", {})
        ch = fetched.get("chars", {})
        sl = fetched.get("sales", {})

        cls_code = str(v.get("class") or u.get("class") or ch.get("class") or "")
        cls_desc, ratio = _cook_class_description(cls_code)

        # Prefer Board of Review -> Certified -> Mailed assessed values
        land_av = _safe_float(v.get("board_land") or v.get("certified_land") or v.get("mailed_land"))
        bldg_av = _safe_float(v.get("board_bldg") or v.get("certified_bldg") or v.get("mailed_bldg"))
        tot_av = _safe_float(v.get("board_tot") or v.get("certified_tot") or v.get("mailed_tot")) or (land_av + bldg_av)

        est_fmv = round(tot_av / ratio, 0) if (tot_av > 0 and ratio > 0) else 0.0
        est_land_fmv = round(land_av / ratio, 0) if (land_av > 0 and ratio > 0) else 0.0
        est_bldg_fmv = round(bldg_av / ratio, 0) if (bldg_av > 0 and ratio > 0) else 0.0

        situs_parts = [
            str(a.get("prop_address_full") or "").strip(),
            str(a.get("prop_address_city_name") or "").strip(),
            str(a.get("prop_address_state") or "IL").strip(),
            str(a.get("prop_address_zipcode_1") or u.get("zip_code") or "").strip(),
        ]
        situs = ", ".join([p for p in [situs_parts[0], situs_parts[1]] if p])
        if situs_parts[2] or situs_parts[3]:
            situs = f"{situs}, {situs_parts[2]} {situs_parts[3]}".strip(", ")

        owner = str(a.get("owner_address_name") or a.get("mail_address_name") or "See Cook Assessor Portal").strip()
        mail_full = str(a.get("mail_address_full") or a.get("owner_address_full") or "").strip()
        mail_city = str(a.get("mail_address_city_name") or a.get("owner_address_city_name") or "").strip()
        mail_st = str(a.get("mail_address_state") or a.get("owner_address_state") or "").strip()
        mail_zip = str(a.get("mail_address_zipcode_1") or a.get("owner_address_zipcode_1") or "").strip()
        mailing = ", ".join([p for p in [mail_full, mail_city, f"{mail_st} {mail_zip}".strip()] if p])

        land_sf = _safe_float(ch.get("char_land_sf"))
        acres = round(land_sf / 43560.0, 3) if land_sf > 0 else 0.0
        bldg_sf = _safe_float(ch.get("char_bldg_sf"))
        yr_built = str(ch.get("char_yrblt") or "").replace(".0", "")
        beds = str(ch.get("char_beds") or "").replace(".0", "")
        fbath = str(ch.get("char_fbath") or "").replace(".0", "")

        lat = _safe_float(u.get("lat")) or None
        lon = _safe_float(u.get("lon")) or None
        pin_fmt = format_il_pin(pin14, "cook")
        links = _build_county_links("cook", pin14)

        rec = {
            "state": "IL",
            "county": "Cook",
            "county_key": "cook",
            "region": IL_COUNTIES_31["cook"]["region"],
            "parcel": pin_fmt,
            "state_parcel_id": pin14,
            "data_source": f"Cook County Open Data Socrata ({v.get('year') or u.get('year') or CURRENT_TAX_YEAR})",
            "is_live_api": True,
            "owner": owner,
            "situs_address": situs or f"{u.get('township_name', 'Cook County')}, IL",
            "mailing_address": mailing,
            "township": str(u.get("township_name") or v.get("township_name") or ""),
            "municipality": str(u.get("municipality_name") or ""),
            "tax_code": str(u.get("tax_code") or ""),
            "tif_district": str(u.get("tif_agencynum") or ""),
            "prop_type": cls_desc,
            "prop_class": cls_code,
            "assessment_ratio": ratio,
            "assessed_val": tot_av,
            "land_assessed": land_av,
            "imp_assessed": bldg_av,
            "actual_val": est_fmv,
            "land_val": est_land_fmv,
            "imp_val": est_bldg_fmv,
            "total_billed": 0.0,
            "acres": acres,
            "sqft": land_sf,
            "bldg_sqft": bldg_sf,
            "year_built": yr_built,
            "beds": beds,
            "baths": fbath,
            "sale_price": _safe_float(sl.get("sale_price")),
            "sale_date": str(sl.get("sale_date") or "")[:10],
            "doc_num": str(sl.get("doc_no") or ""),
            "legal": f"Cook County PIN {pin_fmt} | Twp: {u.get('township_name') or 'N/A'} | NBHD: {u.get('nbhd_code') or v.get('nbhd') or 'N/A'}",
            "lat": lat,
            "lon": lon,
            "google_maps_url": f"https://www.google.com/maps?q={lat},{lon}" if (lat and lon) else "",
            **links,
        }
        results.append(grade_illinois_parcel(rec))

    return results


# ==================== GENERIC ARCGIS LIVE ENGINE FOR 21 DOWNSTATE/COLLAR COUNTIES ====================
def fetch_arcgis_il_county(county_key: str, query_str: str, timeout: int = 8) -> List[Dict[str, Any]]:
    """Query a verified live Illinois County ArcGIS FeatureServer/MapServer by PIN, Address, or Owner."""
    meta = IL_COUNTIES_31.get(county_key)
    if not meta or meta.get("api_type") != "arcgis" or not meta.get("arcgis_url"):
        return []

    url = meta["arcgis_url"]
    q_raw = str(query_str or "").strip()
    q_safe = q_raw.replace("'", "''")
    digits = clean_pin_digits(q_raw)
    pin_fmt = format_il_pin(digits, county_key) if digits else q_raw

    where_clauses = []
    # 1. PIN match (try exact dashless AND formatted hyphenated PIN across county's PIN fields)
    if len(digits) >= 8 and (len(digits) / max(len(re.sub(r"[\s\-\.]", "", q_raw)), 1) > 0.7):
        pin_preds = []
        for pf in meta.get("pin_fields", []):
            pin_preds.append(f"{pf} = '{digits}'")
            if pin_fmt != digits:
                pin_preds.append(f"{pf} = '{pin_fmt}'")
            if q_safe not in (digits, pin_fmt):
                pin_preds.append(f"{pf} = '{q_safe}'")
        if pin_preds:
            where_clauses.append("(" + " OR ".join(pin_preds) + ")")
    else:
        # 2. Address / Owner search
        q_up = q_safe.upper()
        text_preds = []
        for af in meta.get("addr_fields", []):
            text_preds.append(f"UPPER({af}) LIKE '%{q_up}%'")
        for of in meta.get("owner_fields", []):
            text_preds.append(f"UPPER({of}) LIKE '%{q_up}%'")
        if text_preds:
            where_clauses.append("(" + " OR ".join(text_preds) + ")")

    if not where_clauses:
        return []

    params = {
        "where": where_clauses[0],
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "resultRecordCount": 3,
        "f": "json",
    }

    try:
        r = requests.get(
            f"{url}/query",
            params=params,
            timeout=timeout,
            verify=False,
            headers={"User-Agent": "IllinoisRealEstateBot/1.0"},
        )
        if r.status_code != 200:
            return []
        data = r.json()
        # Fallback for older ArcGIS 10.x servers that reject resultRecordCount
        if "error" in data:
            params.pop("resultRecordCount", None)
            r = requests.get(f"{url}/query", params=params, timeout=timeout, verify=False, headers={"User-Agent": "IllinoisRealEstateBot/1.0"})
            data = r.json()
        feats = data.get("features") or []
    except Exception:
        return []

    fm = meta.get("field_map", {})
    results = []
    for feat in feats[:3]:
        att = feat.get("attributes") or {}
        geom = feat.get("geometry")

        raw_pin = _first_val(att, fm.get("pin", [])) or q_raw
        p_digits = clean_pin_digits(raw_pin)
        p_fmt = format_il_pin(p_digits, county_key) if p_digits else raw_pin

        # Owner
        owner = _first_val(att, fm.get("owner", []))
        if not owner and fm.get("owner_parts"):
            owner = " ".join(str(att.get(k) or "").strip() for k in fm["owner_parts"]).strip()
            owner = re.sub(r"\s+", " ", owner)

        # Situs address
        situs_line = _first_val(att, fm.get("situs", []))
        if not situs_line and fm.get("situs_parts"):
            situs_line = " ".join(str(att.get(k) or "").strip() for k in fm["situs_parts"]).strip()
            situs_line = re.sub(r"\s+", " ", situs_line)
        situs_line = situs_line.replace("~", ", ")
        s_city = _first_val(att, fm.get("situs_city", []))
        s_st = _first_val(att, fm.get("situs_state", [])) or "IL"
        s_zip = _first_val(att, fm.get("situs_zip", []))
        s_csz = _first_val(att, fm.get("situs_csz", []))
        if s_csz:
            situs = f"{situs_line}, {s_csz}".strip(", ")
        elif s_city:
            situs = f"{situs_line}, {s_city}, {s_st} {s_zip}".strip(", ")
        else:
            situs = situs_line

        # Mailing address
        m_line = _first_val(att, fm.get("mail_addr", [])).replace("~", ", ")
        m_csz = _first_val(att, fm.get("mail_csz", []))
        m_city = _first_val(att, fm.get("mail_city", []))
        m_st = _first_val(att, fm.get("mail_state", []))
        m_zip = _first_val(att, fm.get("mail_zip", []))
        if m_csz:
            mailing = f"{m_line}, {m_csz}".strip(", ")
        elif m_city:
            mailing = f"{m_line}, {m_city}, {m_st} {m_zip}".strip(", ")
        else:
            mailing = m_line

        # Legal
        legal = _first_val(att, fm.get("legal", [])).replace("~", " ")
        if not legal and fm.get("legal_parts"):
            legal = " ".join(str(att.get(k) or "").strip() for k in fm["legal_parts"]).strip()

        # Valuation: Illinois downstate assessed value = 33.33% of Fair Cash Value (FMV = Assessed * 3)
        total_fcv = _safe_float(_first_val(att, fm.get("total_fcv", [])))
        land_fcv = _safe_float(_first_val(att, fm.get("land_fcv", [])))
        imp_fcv = _safe_float(_first_val(att, fm.get("imp_fcv", [])))

        land_av = _sum_vals(att, fm.get("land_val_parts", []))
        imp_av = _sum_vals(att, fm.get("imp_val_parts", []))
        assessed = _safe_float(_first_val(att, fm.get("assessed_val", []))) or (land_av + imp_av)

        if total_fcv > 0:
            actual_fmv = total_fcv
            land_val = land_fcv if land_fcv > 0 else round(land_av * 3.0, 0)
            imp_val = imp_fcv if imp_fcv > 0 else round(imp_av * 3.0, 0)
        elif assessed > 0:
            actual_fmv = round(assessed * 3.0, 0)
            land_val = round(land_av * 3.0, 0)
            imp_val = round(imp_av * 3.0, 0)
        else:
            actual_fmv = 0.0
            land_val = 0.0
            imp_val = 0.0

        # Acreage / SqFt (fallback to Shape__Area if in sq ft)
        acres = _safe_float(_first_val(att, fm.get("acres", [])))
        sqft = _safe_float(_first_val(att, fm.get("sqft", [])))
        if acres <= 0 and sqft > 100:
            acres = round(sqft / 43560.0, 3)
        elif acres <= 0:
            shape_a = _safe_float(att.get("Shape__Area") or att.get("Shape_Area") or att.get("SHAPE.STArea()") or att.get("Shape.STArea()"))
            if 500 <= shape_a <= 500_000_000:
                acres = round(shape_a / 43560.0, 2)

        # Coordinates
        lat = _safe_float(_first_val(att, fm.get("lat", []))) or None
        lon = _safe_float(_first_val(att, fm.get("lon", []))) or None
        if not (lat and lon):
            lat, lon = _centroid_from_geometry(geom)

        weblink = _first_val(att, fm.get("weblink", []))
        if weblink and not weblink.lower().startswith("http"):
            weblink = ""
        links = _build_county_links(county_key, p_digits or raw_pin, weblink=weblink)

        sale_date_raw = _first_val(att, fm.get("sale_date", []))
        if sale_date_raw.isdigit() and len(sale_date_raw) >= 12:
            try:
                sale_date_raw = datetime.utcfromtimestamp(int(sale_date_raw) / 1000.0).strftime("%Y-%m-%d")
            except Exception:
                pass
        else:
            sale_date_raw = sale_date_raw[:10]

        # Installment payment flags (e.g., Tazewell live payment dates!)
        inst1 = _first_val(att, fm.get("install1_paid", []))
        inst2 = _first_val(att, fm.get("install2_paid", []))
        tax_note = ""
        if inst1 or inst2:
            tax_note = f"Inst1 Paid: {inst1[:10] or 'Unpaid'} | Inst2 Paid: {inst2[:10] or 'Unpaid'}"

        rec = {
            "state": "IL",
            "county": meta["name"],
            "county_key": county_key,
            "region": meta["region"],
            "parcel": p_fmt,
            "state_parcel_id": p_digits or raw_pin,
            "data_source": f"{meta['name']} County Live GIS API",
            "is_live_api": True,
            "owner": owner or "See County Assessor Portal",
            "situs_address": situs or f"{meta['name']} County, IL (See Legal)",
            "mailing_address": mailing,
            "township": _first_val(att, fm.get("township", [])),
            "municipality": _first_val(att, fm.get("municipality", [])),
            "subdivision": _first_val(att, fm.get("subdivision", [])),
            "tax_code": _first_val(att, fm.get("tax_code", [])),
            "prop_type": _first_val(att, fm.get("prop_class", [])) or "Illinois Real Property",
            "prop_class": _first_val(att, fm.get("prop_class", [])),
            "zoning": _first_val(att, fm.get("zoning", [])),
            "flood": _first_val(att, fm.get("flood", [])),
            "exempt_code": _first_val(att, fm.get("exempt_code", [])),
            "tax_status": _first_val(att, fm.get("tax_status", [])),
            "tax_payment_note": tax_note,
            "assessment_ratio": 0.3333,
            "assessed_val": assessed,
            "land_assessed": land_av,
            "imp_assessed": imp_av,
            "actual_val": actual_fmv,
            "land_val": land_val,
            "imp_val": imp_val,
            "total_billed": _safe_float(_first_val(att, fm.get("tax_billed", []))),
            "tax_rate": _safe_float(_first_val(att, fm.get("tax_rate", []))),
            "acres": round(acres, 3) if acres > 0 else 0.0,
            "sqft": sqft,
            "bldg_sqft": _safe_float(_first_val(att, fm.get("bldg_sqft", []))),
            "year_built": _first_val(att, fm.get("year_built", [])).replace(".0", ""),
            "beds": _first_val(att, fm.get("beds", [])).replace(".0", ""),
            "baths": _first_val(att, fm.get("baths", [])).replace(".0", ""),
            "sale_price": _safe_float(_first_val(att, fm.get("sale_price", []))),
            "sale_date": sale_date_raw,
            "doc_num": _first_val(att, fm.get("doc_num", [])),
            "legal": legal,
            "lat": lat,
            "lon": lon,
            "google_maps_url": f"https://www.google.com/maps?q={lat},{lon}" if (lat and lon) else "",
            **links,
        }
        results.append(grade_illinois_parcel(rec))

    return results


# ==================== PORTAL-ONLY FALLBACK DOSSIER BUILDER ====================
def build_portal_fallback_record(county_key: str, query_str: str) -> Dict[str, Any]:
    """Build a structured Illinois Parcel Dossier with direct County Portal / DevNet Wedge deep-links."""
    meta = IL_COUNTIES_31[county_key]
    digits = clean_pin_digits(query_str)
    pin_fmt = format_il_pin(digits, county_key) if digits else str(query_str).strip()
    links = _build_county_links(county_key, digits or pin_fmt)

    # Decode standard IL PIN components (Township-Section-Block-Parcel)
    twp_note = ""
    if len(digits) >= 10:
        twp_note = f"Twp {digits[0:2]} | Sec {digits[2:4]} | Block {digits[4:7]} | Parcel {digits[7:10]}"

    rec = {
        "state": "IL",
        "county": meta["name"],
        "county_key": county_key,
        "region": meta["region"],
        "parcel": pin_fmt,
        "state_parcel_id": digits or pin_fmt,
        "data_source": f"{meta['name']} County Official Portal Deep-Link (reCAPTCHA-protected web portal)",
        "is_live_api": False,
        "owner": "Open Direct Assessor / DevNet Wedge Link Below",
        "situs_address": f"{meta['name']} County, IL (Verify via Assessor Portal)",
        "mailing_address": "",
        "township": twp_note,
        "prop_type": "Illinois Real Property (Portal Lookup)",
        "assessed_val": 0.0,
        "actual_val": 0.0,
        "land_val": 0.0,
        "imp_val": 0.0,
        "total_billed": 0.0,
        "acres": 0.0,
        "legal": f"Standard Illinois PIN Anatomy: {twp_note or pin_fmt}",
        "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(meta['name'] + ' County Illinois')}",
        **links,
    }
    return grade_illinois_parcel(rec)


# ==================== UNDERWRITING & STATUTORY YIELD ENGINE ====================
def grade_illinois_parcel(d: Dict[str, Any]) -> Dict[str, Any]:
    """Apply Illinois-specific tax lien underwriting (35 ILCS 200) and risk screening."""
    owner_up = str(d.get("owner") or "").upper()
    situs_up = str(d.get("situs_address") or "").upper()
    mail_up = str(d.get("mailing_address") or "").upper()
    cls_up = str(d.get("prop_type") or d.get("prop_class") or "").upper()
    flood_up = str(d.get("flood") or "").upper()
    exempt_up = str(d.get("exempt_code") or "").upper()

    act = float(d.get("actual_val") or 0.0)
    imp = float(d.get("imp_val") or 0.0)
    billed = float(d.get("total_billed") or d.get("face_amount") or 0.0)
    tvr = round((billed / act) * 100.0, 2) if (act > 0 and billed > 0) else 0.0
    d["tvr_pct"] = tvr

    # Absentee check
    situs_num = re.findall(r"^\d+", situs_up)
    mail_num = re.findall(r"^\d+", mail_up)
    is_absentee = bool(mail_up and situs_up and (
        (situs_num and mail_num and situs_num[0] != mail_num[0])
        or ("IL" not in mail_up and len(mail_up) > 8)
    ))
    d["is_absentee"] = is_absentee

    # 2026 IL Statutory Penalty Projections (35 ILCS 200/21-215, P.A. 103-0555: max 9% per 6 months = 18%/yr)
    base_tax = billed if billed > 0 else 0.0
    d["il_penalty_6m_max"] = round(base_tax * 0.09, 2)
    d["il_penalty_12m_max"] = round(base_tax * 0.18, 2)
    d["il_penalty_24m_max"] = round(base_tax * 0.36, 2)

    is_exempt = (
        "EXEMPT" in cls_up
        or cls_up.startswith("EX")
        or (exempt_up not in ("", "0", "N", "NONE"))
        or any(k in owner_up for k in [
            "FOREST PRESERVE", "COUNTY OF ", "CITY OF ", "VILLAGE OF ",
            "STATE OF ILLINOIS", "SCHOOL DIST", "PARK DIST", "CHURCH", "MINISTRIES",
            "CEMETERY", "TOWNSHIP", "RAILROAD", "IDOT"
        ])
    )
    is_floodway = "FLOODWAY" in flood_up

    if is_exempt:
        d["grade"] = "Grade F (Trap)"
        d["bid_decision"] = "DO NOT BID — Tax-Exempt / Public Entity Parcel"
        d["why_pick"] = f"TRAP: Tax-exempt or government/religious parcel ({owner_up[:60]} / {cls_up[:40]}). Exempt parcels cannot be validly sold for taxes."
    elif is_floodway and imp <= 0:
        d["grade"] = "Grade D (Caution)"
        d["bid_decision"] = "CAUTION — Mapped FEMA Floodway (Unimproved)"
        d["why_pick"] = f"Parcel lies in mapped FLOODWAY ({flood_up}) with no structure value. Verify buildability before bidding."
    elif not d.get("is_live_api") and act <= 0:
        d["grade"] = "Portal Verify"
        d["bid_decision"] = "VERIFY ON COUNTY PORTAL — Check Delinquency & EAV"
        d["why_pick"] = f"Live GIS API unavailable or reCAPTCHA-gated for {d.get('county')} County. Tap the direct Assessor/DevNet Wedge link below to confirm FMV, prior tax sales, and redemption balance."
    elif act >= 120000 and (tvr == 0 or tvr <= 4.5):
        d["grade"] = "Grade A"
        d["bid_decision"] = "STRONG IL LIEN CANDIDATE (Bid Down Penalty <= 9%/6mo)"
        d["why_pick"] = (
            f"High-equity {d.get('prop_type')} (Est. FMV ${act:,.0f}; Imps ${imp:,.0f})"
            + (f" at {tvr:.2f}% TVR" if tvr > 0 else "")
            + (" — Absentee Owner." if is_absentee else " — Local/Owner-Occupied.")
        )
    elif act >= 40000 and (tvr == 0 or tvr <= 6.5):
        d["grade"] = "Grade B"
        d["bid_decision"] = "QUALIFIED IL LIEN CANDIDATE (Verify Tax Delinquency)"
        d["why_pick"] = (
            f"Solid collateral (Est. FMV ${act:,.0f})"
            + (f", TVR {tvr:.2f}%" if tvr > 0 else "")
            + ". Confirm delinquent tax status & prior unredeemed sales on County Treasurer portal."
        )
    elif act > 0:
        d["grade"] = "Grade C"
        d["bid_decision"] = "SPECULATIVE / LOW-VALUE PARCEL — Check Demolition & Municipal Liens"
        d["why_pick"] = f"Lower market value (Est. FMV ${act:,.0f}). In Illinois, always check municipal weed/demolition liens and scavenger/trustee history."
    else:
        d["grade"] = "GIS Verified"
        d["bid_decision"] = "PARCEL CONFIRMED IN GIS — Verify Valuation & Tax Bill"
        d["why_pick"] = f"Parcel boundary & identifiers confirmed live in {d.get('county')} County GIS. Open the Assessor / Treasurer link below to verify current EAV and tax delinquency."

    return d


# ==================== MASTER DYNAMIC SEARCH ROUTER ====================
def search_illinois_parcel(raw_query: str, county_override: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Dynamically look up any Illinois parcel by PIN, Address, or Owner across all 31 counties.
    - If county_override is given (e.g., /dupage 06-15-117-021 or 'Cook 33-31-402-022-0000'),
      queries that county directly (with portal fallback if portal-only).
    - If no county is specified, auto-detects likely county from PIN length/format and fans
      out in parallel across live Illinois county GIS/Socrata APIs!
    """
    q = str(raw_query or "").strip()
    ck = normalize_il_county(county_override)

    # Extract county name if embedded inside raw_query
    if not ck:
        for alias in sorted(IL_COUNTY_ALIASES.keys(), key=len, reverse=True):
            pat = rf"\b{re.escape(alias)}(?:\s+county)?\b"
            if re.search(pat, q, re.I):
                ck = IL_COUNTY_ALIASES[alias]
                q = re.sub(pat, " ", q, flags=re.I).strip()
                break
        q = re.sub(r"^(?:IL|Illinois)\b|\b(?:IL|Illinois)$", "", q, flags=re.I).strip(" ,;-")

    # 1. Targeted Single-County Lookup
    if ck and ck in IL_COUNTIES_31:
        meta = IL_COUNTIES_31[ck]
        if meta["api_type"] == "cook_socrata":
            hits = fetch_cook_county_live(q)
            if hits:
                return hits
            return [build_portal_fallback_record(ck, q)] if len(clean_pin_digits(q)) >= 10 else []
        elif meta["api_type"] == "arcgis":
            hits = fetch_arcgis_il_county(ck, q, timeout=10)
            if hits:
                return hits
            # If a valid-looking PIN wasn't in GIS snapshot, still return helpful county deep-link card
            if len(clean_pin_digits(q)) >= 8:
                return [build_portal_fallback_record(ck, q)]
            return []
        else:
            # Portal-only county (DevNet Wedge / Sangamon / Winnebago)
            return [build_portal_fallback_record(ck, q)]

    # 2. Auto-Routing When User Sends ONLY a Raw Illinois PIN (No County Name!)
    digits = clean_pin_digits(q)
    if re.match(r"^\d{2}-\d{2}\.\d-\d{3}-\d{3}$", q):
        # Dotted 11-digit PIN -> St. Clair (live) or Sangamon (portal)
        hits = fetch_arcgis_il_county("stclair", q, timeout=8)
        return hits if hits else [build_portal_fallback_record("sangamon", q)]

    if len(digits) == 14:
        hits = fetch_cook_county_live(q)
        return hits

    if len(digits) == 15:
        return fetch_arcgis_il_county("madison", q, timeout=8)

    if len(digits) == 16:
        return fetch_arcgis_il_county("will", q, timeout=8)

    if len(digits) == 12:
        found: List[Dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(AUTO_FANOUT_12DIGIT)) as ex:
            futs = [ex.submit(fetch_arcgis_il_county, c, q, 6) for c in AUTO_FANOUT_12DIGIT]
            for fut in concurrent.futures.as_completed(futs):
                try:
                    found.extend(fut.result() or [])
                except Exception:
                    pass
        return found[:3]

    if len(digits) == 10 and is_illinois_pin_pattern(q):
        found = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(fetch_arcgis_il_county, c, q, 6) for c in AUTO_FANOUT_10DIGIT]
            for fut in concurrent.futures.as_completed(futs):
                try:
                    res = fut.result() or []
                    if res:
                        found.extend(res)
                except Exception:
                    pass
        return found[:3]

    return []


# ==================== TELEGRAM HTML FORMATTERS ====================
def format_illinois_dossier_html(d: Dict[str, Any]) -> str:
    """Render a sleek Telegram HTML dossier card for any Illinois parcel."""
    esc = html.escape
    county = esc(str(d.get("county") or "Illinois").upper())
    ck = d.get("county_key") or normalize_il_county(d.get("county")) or "cook"
    parcel = esc(str(d.get("parcel") or "N/A"))
    raw_pin = esc(str(d.get("state_parcel_id") or ""))
    owner = esc(str(d.get("owner") or "N/A"))
    situs = esc(str(d.get("situs_address") or "See Assessor Portal"))
    mailing = esc(str(d.get("mailing_address") or ""))
    twp = esc(str(d.get("township") or ""))
    muni = esc(str(d.get("municipality") or ""))
    tax_code = esc(str(d.get("tax_code") or ""))
    prop_type = esc(str(d.get("prop_type") or "Illinois Real Property"))
    zoning = esc(str(d.get("zoning") or ""))
    flood = esc(str(d.get("flood") or ""))
    legal = esc(str(d.get("legal") or "N/A"))
    source = esc(str(d.get("data_source") or "Illinois County GIS"))

    grade = str(d.get("grade") or "GIS Verified")
    decision = esc(str(d.get("bid_decision") or ""))
    why = esc(str(d.get("why_pick") or ""))

    act = float(d.get("actual_val") or 0.0)
    ass = float(d.get("assessed_val") or 0.0)
    land = float(d.get("land_val") or 0.0)
    imp = float(d.get("imp_val") or 0.0)
    billed = float(d.get("total_billed") or 0.0)
    tvr = float(d.get("tvr_pct") or 0.0)
    acres = float(d.get("acres") or 0.0)
    bldg_sf = float(d.get("bldg_sqft") or 0.0)
    yr_built = esc(str(d.get("year_built") or ""))
    sale_price = float(d.get("sale_price") or 0.0)
    sale_date = esc(str(d.get("sale_date") or ""))
    doc_num = esc(str(d.get("doc_num") or ""))
    tax_pay_note = esc(str(d.get("tax_payment_note") or ""))

    if "Grade A" in grade:
        badge = "🟢"
    elif "Grade B" in grade:
        badge = "🟡"
    elif "Grade C" in grade or "GIS" in grade or "Portal" in grade:
        badge = "🟠"
    else:
        badge = "🔴"

    ratio_label = "10%/25% Cook" if ck == "cook" else "33.33% IL EAV"
    absentee_txt = "🔴 YES (Absentee)" if d.get("is_absentee") else "🟢 Local / Unconfirmed"

    lines = [
        f"🌽 <b>{county} COUNTY, IL — LIVE TAX LIEN DOSSIER</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏷️ <b>PIN:</b> <code>{parcel}</code>" + (f" (Raw: <code>{raw_pin}</code>)" if raw_pin and raw_pin != parcel else ""),
        f"{badge} <b>Underwriting:</b> <b>{esc(grade)}</b> — <b>{decision}</b>",
        f"📡 <b>Source:</b> <i>{source}</i>",
        "",
        f"📍 <b>Property Address:</b> <code>{situs}</code>",
        f"👤 <b>Owner / Taxpayer:</b> <code>{owner}</code>",
    ]
    if mailing:
        lines.append(f"📬 <b>Mailing:</b> <code>{mailing}</code> | <b>Absentee:</b> {absentee_txt}")
    if twp or muni or tax_code:
        loc_bits = [b for b in [f"Twp: {twp}" if twp else "", f"Muni: {muni}" if muni else "", f"TaxCode: {tax_code}" if tax_code else ""] if b]
        lines.append("🏛️ <b>District:</b> " + " | ".join(loc_bits))

    prop_line = f"🏗️ <b>Class / Type:</b> {prop_type}"
    if zoning:
        prop_line += f" | <b>Zoning:</b> {zoning}"
    if flood:
        prop_line += f" | ⚠️ <b>Flood:</b> {flood}"
    lines.append(prop_line)

    dim_bits = []
    if acres > 0:
        dim_bits.append(f"<b>{acres:.2f} Acres</b>")
    if bldg_sf > 0:
        dim_bits.append(f"<b>{bldg_sf:,.0f} sq ft</b> bldg")
    if yr_built:
        dim_bits.append(f"Built <b>{yr_built}</b>")
    if d.get("beds") or d.get("baths"):
        dim_bits.append(f"{esc(str(d.get('beds') or '?'))}bd/{esc(str(d.get('baths') or '?'))}ba")
    if dim_bits:
        lines.append("📐 <b>Specs:</b> " + " | ".join(dim_bits))

    lines.append("")
    lines.append(f"💰 <b>ILLINOIS VALUATION &amp; STATUTORY YIELD ({ratio_label}):</b>")
    if act > 0 or ass > 0:
        lines.append(f"• <b>Est. Full Market Value:</b> <b>${act:,.0f}</b> (Assessed/EAV: <code>${ass:,.0f}</code>)")
        if land > 0 or imp > 0:
            lines.append(f"  ├─ Land Est. Val: <b>${land:,.0f}</b> | Imps Est. Val: <b>${imp:,.0f}</b>")
    else:
        lines.append("• <b>Valuation:</b> Verify EAV / Market Value on County Assessor link below")

    if billed > 0:
        lines.append(f"• <b>Annual Tax / Face Due:</b> <b>${billed:,.2f}</b>" + (f" (TVR: <b>{tvr:.2f}%</b>)" if tvr > 0 else ""))
        lines.append(
            f"• <b>2026 IL Max Penalty (<code>9%/6mo</code> = <code>18%/yr</code>):</b> "
            f"6m: <b>+${d.get('il_penalty_6m_max', 0):,.2f}</b> | "
            f"12m: <b>+${d.get('il_penalty_12m_max', 0):,.2f}</b> | "
            f"24m: <b>+${d.get('il_penalty_24m_max', 0):,.2f}</b>"
        )
    else:
        lines.append("• <b>2026 IL Penalty Rate (35 ILCS 200/21-215):</b> Bid-down from <b>9%/6mo (18%/yr max)</b> + <b>12%/yr</b> sub-taxes <i>(pre-2024 was 18%/6mo)</i>")

    if tax_pay_note:
        lines.append(f"• <b>Tax Installments:</b> <code>{tax_pay_note}</code>")
    if sale_price > 0 or sale_date:
        sale_str = f"${sale_price:,.0f}" if sale_price > 0 else "Recorded"
        lines.append(f"• <b>Last Recorded Sale:</b> <b>{sale_str}</b> ({sale_date or 'N/A'})" + (f" | Doc: <code>{doc_num}</code>" if doc_num else ""))

    lines.extend([
        "",
        "📜 <b>UNDERWRITING &amp; REDEMPTION:</b>",
        f"• <b>Verdict:</b> {why}",
        "• <b>IL Redemption:</b> <code>2.5 yrs</code> (1-6u Res) | <code>2 yrs</code> (Vacant/Other) | <code>6 mos</code> (Comm/2+yr Vacant)",
    ])
    if legal and legal != "N/A":
        lines.append(f"• <b>Legal:</b> <code>{legal[:220]}</code>")

    # Clickable HTML links
    link_parts = []
    if d.get("dossier_url"):
        link_parts.append(f'<a href="{esc(d["dossier_url"])}">📄 Live Web Dossier</a>')
    if d.get("assessor_link"):
        link_parts.append(f'<a href="{esc(d["assessor_link"])}">🏛️ Assessor / Property Card</a>')
    if d.get("treasurer_link"):
        link_parts.append(f'<a href="{esc(d["treasurer_link"])}">💵 Treasurer / Tax Sale</a>')
    if d.get("google_maps_url"):
        link_parts.append(f'<a href="{esc(d["google_maps_url"])}">📍 Google Maps</a>')
    if d.get("trustee_link"):
        link_parts.append(f'<a href="{esc(d["trustee_link"])}">📋 ILTaxSale Trustee OTC</a>')

    lines.append("")
    lines.append(" | ".join(link_parts[:3]))
    if len(link_parts) > 3:
        lines.append(" | ".join(link_parts[3:]))

    return "\n".join(lines)


def format_illinois_county_card_html(county_key: str) -> str:
    """Render a county command card when the user sends /cook, /dupage, /il kane, etc."""
    esc = html.escape
    ck = normalize_il_county(county_key)
    if not ck or ck not in IL_COUNTIES_31:
        return format_illinois_overview_html()

    m = IL_COUNTIES_31[ck]
    api_badge = "🟢 LIVE DIRECT API" if m["api_type"] in ("arcgis", "cook_socrata") else "🔗 OFFICIAL PORTAL DEEP-LINK"
    ex_pin = m["pin_example"]
    assessor_home = m["assessor_url"].replace("{pin_digits}", clean_pin_digits(ex_pin)).replace("{tax_year}", str(CURRENT_TAX_YEAR))

    lines = [
        f"🌽 <b>{esc(m['name'].upper())} COUNTY, ILLINOIS — TAX LIEN HUB</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📡 <b>Live Engine Mode:</b> <b>{api_badge}</b>",
        f"🗺️ <b>Region:</b> {esc(m['region'])}",
        f"🔢 <b>PIN Format ({m['pin_digits']} digits):</b> <code>{esc(ex_pin)}</code>",
        "",
        "⚖️ <b>2026 ILLINOIS STATUTORY RULES (35 ILCS 200):</b>",
        "• <b>Annual Tax Sale Bidding:</b> Bid-down penalty starting at <b>9% per 6 months (18%/yr max)</b> under P.A. 103-0555 <i>(pre-2024 was 18%/6mo = 36%/yr)</i> — <b>NO non-refundable surplus/premium!</b>",
        "• <b>Subsequent Taxes:</b> <b>12%/yr flat</b> (35 ILCS 200/21-355)",
        "• <b>Redemption:</b> <b>2.5 yrs</b> (1–6u Res) | <b>2 yrs</b> (Vacant) | <b>6 mos</b> (Comm/Scavenger)",
        "",
        "🔍 <b>HOW TO QUERY LIVE PARCELS RIGHT NOW:</b>",
        f"• <code>/{ck} {esc(ex_pin)}</code> — Instant live parcel dossier",
        f"• <code>{esc(m['name'])} {esc(ex_pin)}</code> — Natural language lookup",
        f"• <code>/{ck} &lt;Street Name or Owner&gt;</code> — Live address/owner search" if m["api_type"] in ("arcgis", "cook_socrata") else f"• <i>Or drop a {esc(m['name'])} County delinquent tax sale .xlsx/.csv/.pdf into chat to auto-index!</i>",
        "",
        f'🔗 <a href="{esc(assessor_home)}">🏛️ Assessor / DevNet Portal</a> | '
        f'<a href="{esc(m["treasurer_url"].format(pin_digits=clean_pin_digits(ex_pin), tax_year=CURRENT_TAX_YEAR))}">💵 County Treasurer</a> | '
        f'<a href="{esc(m["trustee_url"])}">📋 ILTaxSale Trustee OTC</a>',
    ]
    if m.get("tls_url"):
        lines.append(f'📚 <a href="{esc(m["tls_url"])}">Tax Lien School County Guide</a>')
    return "\n".join(lines)


def format_illinois_overview_html() -> str:
    """Render the full 31-County Illinois Tax Lien Hub overview for /il or /illinois."""
    live_counties = sorted([k for k, v in IL_COUNTIES_31.items() if v["api_type"] in ("arcgis", "cook_socrata")])
    portal_counties = sorted([k for k, v in IL_COUNTIES_31.items() if v["api_type"] == "portal"])

    live_cmds = ", ".join(f"<code>/{k}</code>" for k in live_counties)
    portal_cmds = ", ".join(f"<code>/{k}</code>" for k in portal_counties)

    lines = [
        "🌽 <b>ILLINOIS 31-COUNTY TAX LIEN INTELLIGENCE ENGINE</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "⚖️ <b>Statutory Framework (35 ILCS 200):</b>",
        "• <b>Bidding Format:</b> Bid-down penalty % (0%–9% per 6 mos = <b>18%/yr max</b> under P.A. 103-0555; <i>historically 18%/6mo = 36%/yr pre-2024</i>) — <b>$0 non-refundable premium!</b>",
        "• <b>Subsequent Taxes:</b> <b>12%/yr</b> | <b>Redemption:</b> 2–2.5 yrs (6 mos comm/scavenger)",
        "• <b>Trustee OTC Program:</b> <a href=\"https://iltaxsale.com/\">ILTaxSale.com (Joseph E. Meyer)</a> covers ~94 IL counties",
        "",
        f"🟢 <b>22 LIVE DIRECT-API COUNTIES (Instant Real-Time Parcel Lookup):</b>\n{live_cmds}",
        "",
        f"🔗 <b>9 PORTAL-LINKED COUNTIES (Direct DevNet / Assessor Deep-Links + Upload Indexing):</b>\n{portal_cmds}",
        "",
        "💡 <b>Try Live Lookups Right Now:</b>",
        "• <code>/cook 33-31-402-022-0000</code> <i>(Cook 2026 Live Socrata API)</i>",
        "• <code>/dupage 06-15-117-021</code> <i>(DuPage 86-Field Live GIS)</i>",
        "• <code>/peoria 17-26-329-017</code> <i>(Peoria Live Valuations &amp; Specs)</i>",
        "• <code>/tazewell 23-23-22-307-010</code> <i>(Tazewell Live Tax Installments)</i>",
        "• <code>/stclair 21-35.0-300-010</code> <i>(St. Clair 99-Field Live GIS)</i>",
        "• Or just paste any IL PIN directly (e.g. <code>06-15-117-021</code> or <code>33-31-402-022-0000</code>)!",
    ]
    return "\n".join(lines)
