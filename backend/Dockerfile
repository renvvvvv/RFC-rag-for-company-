FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and common runtime libraries for OCR/PDF/office.
# Each package is installed only if it is not already present.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gcc \
    && if ! command -v tesseract >/dev/null 2>&1; then \
         apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng; \
       fi \
    && if ! command -v pdfinfo >/dev/null 2>&1; then \
         apt-get install -y --no-install-recommends poppler-utils; \
       fi \
    && if ! command -v libreoffice >/dev/null 2>&1; then \
         apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc libreoffice-impress; \
       fi \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies as root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and create a non-root user
COPY . .
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
