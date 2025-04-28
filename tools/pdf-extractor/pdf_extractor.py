# pdf_extractor.py

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import os

class PDFExtractor:
    def __init__(self, tesseract_cmd=None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from PDF. Try direct extraction first, fallback to OCR if needed.
        """
        text = self._extract_direct_text(pdf_path)

        if len(text.strip()) > 50:  # Arbitrary threshold to detect "real" text
            return text

        print(f"[INFO] No text found in {pdf_path} — falling back to OCR.")
        return self._extract_via_ocr(pdf_path)

    def _extract_direct_text(self, pdf_path: str) -> str:
        """
        Direct text extraction using PyMuPDF.
        """
        text = ""
        pdf_document = fitz.open(pdf_path)

        for page in pdf_document:
            text += page.get_text()

        pdf_document.close()
        return text

    def _extract_via_ocr(self, pdf_path: str) -> str:
        """
        OCR extraction using pytesseract.
        """
        text = ""
        pdf_document = fitz.open(pdf_path)

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img)
            text += f"Page {page_num + 1}:\n{ocr_text}\n\n"

        pdf_document.close()
        return text.strip()

if __name__ == "__main__":
    extractor = PDFExtractor(
        tesseract_cmd="/usr/bin/tesseract"  # Adjust if needed
    )
    pdf_path = "example.pdf"
    extracted_text = extractor.extract_text(pdf_path)
    print(extracted_text)
