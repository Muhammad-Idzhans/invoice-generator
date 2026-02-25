# Invoice Extraction & PDF Generator API

A FastAPI-powered service that extracts structured data from invoice documents (PDF/images) using **Azure AI Content Understanding** and generates professionally styled PDF invoices using **Playwright** and **Jinja2** templates.

## Architecture

```
invoice-generator/
├── app/
│   ├── main.py            # FastAPI server with API endpoints
│   ├── template.html      # Jinja2 HTML invoice template
│   ├── requirements.txt   # Python dependencies
│   ├── Dockerfile         # Container configuration
│   └── .env               # Environment variables (not committed)
├── client.py              # CLI client for end-to-end automation
├── invoice-samples-input/  # Sample invoice files for testing
└── invoice-samples-output/ # Generated PDF outputs
```

## How It Works

1. **Upload** an invoice file (PDF, JPG, PNG, TIFF, BMP) to the `/analyze-invoice` endpoint.
2. **Azure AI Content Understanding** extracts structured data — vendor info, customer details, line items, totals, etc.
3. **Send** the extracted JSON to `/generate-pdf` to render a polished A4 invoice PDF using the Jinja2 template and Playwright's Chromium engine.

## API Endpoints

All endpoints are protected with API key authentication via the `X-API-Key` header.

| Method | Endpoint            | Description                                      |
|--------|---------------------|--------------------------------------------------|
| GET    | `/health`           | Verifies Azure AI connection status              |
| POST   | `/analyze-invoice`  | Uploads an invoice file and returns extracted JSON |
| POST   | `/generate-pdf`     | Accepts invoice JSON and returns a PDF file      |

### `POST /analyze-invoice`

- **Content-Type:** `multipart/form-data`
- **Body:** `file` — the invoice document (PDF or image)
- **Returns:** JSON with `status`, `data` (extracted fields), and `raw_result`

**Extracted fields include:**
`InvoiceId`, `InvoiceDate`, `DueDate`, `VendorName`, `VendorAddress`, `VendorTaxId`, `CustomerName`, `CustomerAddress`, `CustomerTaxId`, `LineItems`, `SubtotalAmount`, `TotalTaxAmount`, `TotalDiscountAmount`, `TotalAmount`, `AmountDue`, `PaymentTerm`, and more.

### `POST /generate-pdf`

- **Content-Type:** `application/json`
- **Body:** The `data` object from `/analyze-invoice`, or the full response (auto-unwraps)
- **Returns:** PDF file as a downloadable attachment (`application/pdf`)

## Prerequisites

- **Python 3.10+**
- **Azure AI Content Understanding** resource with a configured analyzer
- Playwright Chromium browser (installed automatically)

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd invoice-generator
```

### 2. Install dependencies

```bash
cd app
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure environment variables

Create `app/.env` with:

```env
AZURE_AI_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
AZURE_AI_KEY=<your-azure-ai-key>
ANALYZER_ID=<your-analyzer-id>
```

### 4. Run the server

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API docs will be available at `http://localhost:8000/docs`.

## Usage

### Using the Client Script

The included `client.py` provides a fully automated workflow — it opens a file picker, extracts invoice data, generates the PDF, and saves it locally:

```bash
python client.py
```

### Using cURL

**Analyze an invoice:**

```bash
curl -X POST http://localhost:8000/analyze-invoice \
  -H "X-API-Key: <your-api-key>" \
  -F "file=@invoice.pdf"
```

**Generate a PDF:**

```bash
curl -X POST http://localhost:8000/generate-pdf \
  -H "X-API-Key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d @extracted_data.json \
  --output invoice_output.pdf
```

## Tech Stack

| Component          | Technology                        |
|--------------------|-----------------------------------|
| Web Framework      | FastAPI + Uvicorn                 |
| Invoice Extraction | Azure AI Content Understanding    |
| Template Engine    | Jinja2                            |
| PDF Rendering      | Playwright (Chromium)             |
| Authentication     | API Key (`X-API-Key` header)      |
