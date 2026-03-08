# Document Information Extraction System

Extract structured information from PDFs and scanned images using OCR (Tesseract) and NLP (spaCy).

## Features

- **OCR Text Extraction** - Extract text from PDFs and images using Tesseract
- **Entity Recognition** - Detect names, dates, amounts, emails, phone numbers, etc.
- **Confidence Scoring** - Every extraction includes confidence levels
- **Web Interface** - Simple, clean UI for uploading and viewing results
- **JSON Export** - Export results as structured JSON

## Quick Start (Windows)

### 1. Install Prerequisites

1. **Python 3.9+**
   - Download from https://python.org
   - Make sure to check "Add Python to PATH" during installation

2. **Tesseract OCR**
   - Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Run the installer
   - **Important**: Add Tesseract to your PATH:
     - Find where Tesseract was installed (usually `C:\Program Files\Tesseract-OCR`)
     - Add this folder to your system PATH environment variable
     - Restart your command prompt

### 2. Start the Backend

### 3. Start the Frontend

The frontend will open in your browser at `http://localhost:8080`


## Running from IDE (VS Code, PyCharm, etc.)

### Backend

1. Open the `backend` folder in your IDE
2Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   python -m spacy download en_core_web_sm
   ```
3Run `main.py`

### Frontend

The frontend is a simple HTML file. You can:

1. **Option 1**: Just double-click `index.html` to open in browser
   - Note: You may need to enable CORS in the backend for this to work

2. **Option 2**: Use a local server:
   ```bash
   # Using Python
   python -m http.server 8080
   
   # Or using Node.js
   npx serve -p 8080
   ```
   Then open `http://localhost:8080`

## API Usage

### Extract from Document

```bash
curl -X POST "http://localhost:8000/extract" \
  -F "file=@document.pdf" \
  -F "min_confidence=0.5"
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Response Format

```json
{
  "success": true,
  "document_id": "abc123",
  "filename": "invoice.pdf",
  "text": "Extracted text...",
  "entities": [
    {
      "type": "date",
      "value": "2024-01-15",
      "confidence": 0.95,
      "confidence_level": "high"
    }
  ],
  "fields": {
    "date": {
      "field_name": "date",
      "value": "2024-01-15",
      "confidence": 0.95,
      "confidence_level": "high",
      "extraction_method": "regex"
    }
  },
  "overall_confidence": 0.89,
  "metadata": {
    "filename": "invoice.pdf",
    "file_type": "pdf",
    "file_size_bytes": 102456,
    "processing_time_seconds": 2.34,
    "pages_processed": 1,
    "ocr_engine": "tesseract",
    "extraction_methods": ["ocr_tesseract", "regex", "nlp_spacy"],
    "timestamp": "2024-01-15T10:30:00"
  }
}
```

## Supported Entity Types

| Type | Description | Example |
|------|-------------|---------|
| person | Person names | John Smith |
| organization | Company names | Acme Corp |
| date | Dates | 2024-01-15 |
| amount | Monetary amounts | $1,234.56 |
| email | Email addresses | user@example.com |
| phone | Phone numbers | 555-123-4567 |
| invoice | Invoice numbers | INV-001 |
| percentage | Percentages | 25% |
| url | URLs | https://example.com |

## Confidence Levels

- **High** (≥85%): Very reliable
- **Medium** (60-84%): Reliable with verification
- **Low** (<60%): Requires manual review

## Troubleshooting

### "Tesseract not found" error

1. Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
2. Add Tesseract to your PATH:
   - Search "Environment Variables" in Windows search
   - Click "Edit the system environment variables"
   - Click "Environment Variables"
   - Find "Path" in System variables, click "Edit"
   - Click "New" and add your Tesseract path (e.g., `C:\Program Files\Tesseract-OCR`)
   - Click OK on all dialogs
   - Restart your command prompt

### "spaCy model not found" error

Run in the backend folder (with venv activated):
```bash
python -m spacy download en_core_web_sm
```

### CORS errors in browser

Make sure the backend is running and CORS is enabled (it is by default in the code).

### Port already in use

If port 8000 or 8080 is in use, you can change them:
- Backend: Edit `main.py`, change `port=8000` to another port
- Frontend: Use `python -m http.server 8081` for a different port

## Project Structure

```
document-extractor/
├── backend/
│   ├── main.py              # Main FastAPI application
│   ├── requirements.txt     # Python dependencies
│   ├── start.bat           # Windows startup script (CMD)
│   ├── start.ps1           # Windows startup script (PowerShell)
│   └── venv/               # Virtual environment (created automatically)
├── frontend/
│   ├── index.html          # Web interface
│   └── start.bat           # Frontend startup script
└── README.md               # This file
```