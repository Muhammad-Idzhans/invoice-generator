# Playwright base image with Chromium & OS deps pre-installed
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Ensure Chromium matches the Python package version
RUN python -m playwright install chromium

# Copy application files
COPY main.py /app/main.py
COPY template.html /app/template.html

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
