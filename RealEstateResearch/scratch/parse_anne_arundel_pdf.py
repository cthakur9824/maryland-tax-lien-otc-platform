import fitz  # PyMuPDF
import pdfplumber
import json
import os

pdf_path = r"c:\Obsedian\RealEstateResearch\RealEstateResearch\raw\Anne-Arundell-list-of-liens.pdf"

doc = fitz.open(pdf_path)
print("Page count:", len(doc))

for page_num in range(min(3, len(doc))):
    page = doc[page_num]
    text = page.get_text()
    print(f"--- PAGE {page_num+1} (Length: {len(text)}) ---")
    print(text[:1500])
