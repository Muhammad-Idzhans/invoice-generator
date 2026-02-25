"""
Invoice Generator Client
Selects a file → calls /analyze-invoice → calls /generate-pdf → saves the PDF locally.
"""

import os
import sys
import requests
from tkinter import Tk, filedialog
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "app", ".env"))

BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("AZURE_AI_KEY")

def select_file():
    """Open a file picker dialog to select an invoice file."""
    root = Tk()
    root.withdraw()  # Hide the main tkinter window
    file_path = filedialog.askopenfilename(
        title="Select an invoice file",
        filetypes=[
            ("All supported", "*.pdf;*.jpg;*.jpeg;*.png;*.tiff;*.bmp"),
            ("PDF files", "*.pdf"),
            ("Image files", "*.jpg;*.jpeg;*.png;*.tiff;*.bmp"),
        ]
    )
    root.destroy()
    return file_path

def main():
    # 1. Select file
    print("Opening file picker...")
    file_path = select_file()

    if not file_path:
        print("No file selected. Exiting.")
        return

    print(f"Selected: {file_path}")

    headers = {"X-API-Key": API_KEY}

    # 2. Call /analyze-invoice
    print("\n[Step 1] Analyzing invoice...")
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{BASE_URL}/analyze-invoice",
            headers=headers,
            files={"file": (os.path.basename(file_path), f)}
        )

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return

    result = response.json()
    print(f"Extracted {len(result.get('data', {}))} fields.")

    # 3. Call /generate-pdf
    print("\n[Step 2] Generating PDF...")
    pdf_response = requests.post(
        f"{BASE_URL}/generate-pdf",
        headers={**headers, "Content-Type": "application/json"},
        json=result  # Sends the full response; endpoint auto-unwraps
    )

    if pdf_response.status_code != 200:
        print(f"Error: {pdf_response.status_code} - {pdf_response.text}")
        return

    # 4. Save PDF
    invoice_id = result.get("data", {}).get("InvoiceId", "invoice")
    output_file = f"invoice_{invoice_id}.pdf"

    with open(output_file, "wb") as f:
        f.write(pdf_response.content)

    print(f"\n[Done] PDF saved to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()
