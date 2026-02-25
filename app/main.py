import os
import json
import asyncio
import uvicorn
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, Response

from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from dotenv import load_dotenv
load_dotenv()

# Configuration
AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
AI_KEY = os.getenv("AZURE_AI_KEY")
ANALYZER_ID = os.getenv("ANALYZER_ID")

# Will throw an error if the .env file is not set
if not AI_ENDPOINT or not AI_KEY:
    raise ValueError("AZURE_AI_ENDPOINT and AZURE_AI_KEY must be set in the .env file")

# API Key Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != AI_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# Initialize FastAPI with global API key protection
app = FastAPI(
    title="Invoice Extraction and Generator API",
    dependencies=[Depends(verify_api_key)]  # Protects ALL endpoints
)

# Initialize Azure AI Client
client = ContentUnderstandingClient(
    endpoint=AI_ENDPOINT,
    credential=AzureKeyCredential(AI_KEY)
)

# Check the health of the FastAPI application (Check if the Azure AI connection is successful)
@app.get("/health")
async def health_check():
    try:
        # Attempt a lightweight call to verify credentials
        analyzers = client.list_analyzers()
        return {"status": "ok", "message": "Azure AI connection successful"}

    except HttpResponseError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Azure AI connection failed: {e.message}"
        )

@app.post("/analyze-invoice")
async def analyze_invoice(file: UploadFile = File(...)):
    """
    Uploads an invoice PDF/Image, extracts data using Azure AI, 
    and returns structured JSON.
    """
    try:
        # 1. Read the file stream
        file_bytes = await file.read()
        
        # 2. Send to Azure AI Content Understanding
        # We use 'begin_analyze_binary' for binary data (file uploads)
        poller = client.begin_analyze_binary(
            analyzer_id=ANALYZER_ID,
            binary_input=file_bytes,
            content_type=file.content_type or "application/octet-stream"
        )
        
        # 3. Wait for the Long-Running Operation (LRO) to finish
        # Run in a thread to avoid blocking the async event loop
        result = await asyncio.to_thread(poller.result)

        # 4. Extract the 'fields' from the response
        # The result structure depends on your Schema in the Studio.
        # Usually, it's inside result.contents -> fields
        
        def serialize_field(field):
            """
            Convert Azure SDK field objects to clean JSON-serializable types.
            
            Azure Content Understanding fields are dict-like with structure:
            - valueString / valueNumber / valueDate for primitives
            - valueObject for nested objects (recursively process)
            - valueArray for arrays (recursively process)
            - If no value key exists, Azure couldn't extract it → return None
            """
            if field is None:
                return None
            
            # Handle dict-like SDK objects (MutableMapping)
            if hasattr(field, "get") or isinstance(field, dict):
                # Check for actual extracted values in priority order
                for value_key in ["valueString", "valueNumber", "valueDate"]:
                    if value_key in field:
                        return field[value_key]
                
                # Nested object: recursively serialize each sub-field
                if "valueObject" in field:
                    obj = field["valueObject"]
                    return {k: serialize_field(v) for k, v in obj.items()}
                
                # Array: recursively serialize each item
                if "valueArray" in field:
                    return [serialize_field(item) for item in field["valueArray"]]
                
                # No value key found → Azure couldn't extract this field
                return None
            
            # Fallback for non-dict SDK objects (e.g. typed field classes)
            for attr in ["value_string", "value_number", "value_date", "value"]:
                val = getattr(field, attr, None)
                if val is not None:
                    if isinstance(val, (str, int, float, bool)):
                        return val
                    return str(val)
            
            return None

        extracted_data = {}
        
        # We iterate through the contents (pages/documents)
        if result.contents:
            for content in result.contents:
                # 'fields' contains the Key-Value pairs you defined (e.g., CustomerName)
                if hasattr(content, "fields") and content.fields:
                    for field_name, field_value in content.fields.items():
                        extracted_data[field_name] = serialize_field(field_value)

        # Safely serialize the raw result for debugging
        try:
            raw = result.as_dict()
        except Exception:
            raw = str(result)

        return JSONResponse(content={
            "status": "success",
            "data": extracted_data,
            "raw_result": raw
        })

    except HttpResponseError as e:
        raise HTTPException(status_code=e.status_code, detail=f"Azure Error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")



@app.post("/generate-pdf")
async def generate_pdf(invoice_data: dict):
    """
    Accepts extracted invoice data (JSON) and returns a rendered PDF.
    
    Usage: Send the 'data' object from /analyze-invoice as the request body.
    You can also send the full /analyze-invoice response — it will auto-unwrap.
    Returns: PDF file as a downloadable attachment.
    """
    try:
        # Auto-unwrap: if user sent the full /analyze-invoice response,
        # extract just the 'data' object
        if "data" in invoice_data and "status" in invoice_data:
            invoice_data = invoice_data["data"]
        
        # 1. Determine currency from the extracted data
        currency = ""  # default
        total_amount = invoice_data.get("TotalAmount")
        if isinstance(total_amount, dict):
            currency = total_amount.get("CurrencyCode", "")
        
        # 2. Render the HTML template with Jinja2
        template_dir = Path(__file__).parent
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("template.html")
        
        rendered_html = template.render(
            currency=currency,
            **invoice_data  # Spreads all fields as template variables
        )
        
        # 3. Use Playwright to convert the rendered HTML into a PDF
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            await page.set_content(rendered_html, wait_until="networkidle")
            
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                margin={
                    "top": "0mm",
                    "bottom": "0mm",
                    "left": "0mm",
                    "right": "0mm"
                }
            )
            
            await browser.close()
        
        # 4. Return the PDF as a downloadable file
        invoice_id = invoice_data.get("InvoiceId", "invoice")
        filename = f"invoice_{invoice_id}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
