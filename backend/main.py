"""
Document Information Extraction System - Simplified Version
"""

import os
import re
import io
import uuid
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import pytesseract
import spacy
import cv2
import numpy as np
from PIL import Image, ImageEnhance
from pdf2image import convert_from_bytes
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load spaCy model (with fallback)
try:
    nlp = spacy.load("en_core_web_sm")
    logger.info("Loaded spaCy model: en_core_web_sm")
except:
    logger.warning("spaCy model not found. NLP extraction disabled.")
    logger.info("To install: python -m spacy download en_core_web_sm")
    nlp = None

# ============================================================================
# Pydantic Models
# ============================================================================

class Entity(BaseModel):
    type: str
    value: str
    confidence: float
    confidence_level: str
    context: Optional[str] = None

class ExtractedField(BaseModel):
    field_name: str
    value: Any
    confidence: float
    confidence_level: str
    extraction_method: str

class PageResult(BaseModel):
    page_number: int
    text: str
    confidence: float
    word_count: int

class ProcessingMetadata(BaseModel):
    filename: str
    file_type: str
    file_size_bytes: int
    processing_time_seconds: float
    pages_processed: int
    ocr_engine: str
    extraction_methods: List[str]
    timestamp: str
    warnings: List[str] = []

class ExtractionResult(BaseModel):
    success: bool
    document_id: str
    filename: str
    text: str
    pages: List[PageResult]
    entities: List[Entity]
    fields: Dict[str, ExtractedField]
    overall_confidence: float
    metadata: ProcessingMetadata
    error_message: Optional[str] = None

# ============================================================================
# OCR Module
# ============================================================================

def preprocess_image(image: Image.Image) -> Image.Image:
    """Preprocess image for better OCR"""
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        img_array = np.array(image)
        
        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Denoise
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # Convert back to PIL
        processed = Image.fromarray(gray)
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(processed)
        processed = enhancer.enhance(2.0)
        
        return processed
    except Exception as e:
        logger.error(f"Preprocessing error: {e}")
        return image

def extract_text_from_image(image: Image.Image) -> tuple[str, float]:
    """Extract text from image using Tesseract"""
    try:
        image = preprocess_image(image)
        
        data = pytesseract.image_to_data(
            image,
            config='--psm 3 --oem 3',
            output_type=pytesseract.Output.DICT
        )
        
        text_parts = []
        confidences = []
        
        for i, text in enumerate(data['text']):
            if text.strip() and int(data['conf'][i]) > 0:
                text_parts.append(text)
                confidences.append(int(data['conf'][i]))
        
        full_text = ' '.join(text_parts)
        avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
        
        return full_text, avg_confidence
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return "", 0.0

def extract_text_from_pdf(pdf_content: bytes) -> List[tuple[str, float]]:
    """Extract text from PDF"""
    try:
        images = convert_from_bytes(pdf_content, dpi=300)
        results = []
        
        for image in images[:100]:  # Limit to 100 pages
            text, conf = extract_text_from_image(image)
            results.append((text, conf))
        
        return results
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return []

# ============================================================================
# Entity Extraction
# ============================================================================

# Regex patterns
PATTERNS = {
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.I),
    'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b', re.I),
    'ssn': re.compile(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b', re.I),
    'date_us': re.compile(r'\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)?\d{2}\b', re.I),
    'date_iso': re.compile(r'\b(?:19|20)\d{2}[/-](?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])\b', re.I),
    'date_long': re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+(?:19|20)?\d{2}\b', re.I),
    'amount': re.compile(r'\b[$€£¥]\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b', re.I),
    'amount_decimal': re.compile(r'\b\d{1,3}(?:,\d{3})*\.\d{2}\b', re.I),
    'invoice': re.compile(r'\b(?:INV|Invoice|Order|PO)[-#\s]*(\d+[\w-]*)\b', re.I),
    'percentage': re.compile(r'\b\d{1,3}(?:\.\d{1,2})?\s*%\b', re.I),
    'url': re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.I),
}

def get_confidence_level(confidence: float) -> str:
    if confidence >= 0.85:
        return 'high'
    elif confidence >= 0.60:
        return 'medium'
    elif confidence >= 0.40:
        return 'low'
    else:
        return 'unknown'

def extract_regex_entities(text: str) -> List[Entity]:
    """Extract entities using regex patterns"""
    entities = []
    
    type_confidences = {
        'email': 0.95, 'phone': 0.90, 'ssn': 0.95,
        'date_iso': 0.90, 'date_us': 0.85, 'date_long': 0.80,
        'amount': 0.90, 'amount_decimal': 0.75,
        'invoice': 0.85, 'percentage': 0.85, 'url': 0.90
    }
    
    for entity_type, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end]
            
            confidence = type_confidences.get(entity_type, 0.80)
            
            entities.append(Entity(
                type=entity_type.replace('date_', 'date').replace('amount_decimal', 'amount'),
                value=value,
                confidence=confidence,
                confidence_level=get_confidence_level(confidence),
                context=context
            ))
    
    return entities

def extract_nlp_entities(text: str) -> List[Entity]:
    """Extract entities using spaCy NLP"""
    if not nlp:
        return []
    
    entities = []
    
    try:
        doc = nlp(text[:100000])  # Limit text length
        
        type_mapping = {
            'PERSON': 'person',
            'ORG': 'organization',
            'GPE': 'location',
            'DATE': 'date',
            'MONEY': 'amount',
            'PERCENT': 'percentage'
        }
        
        for ent in doc.ents:
            if ent.label_ in type_mapping:
                confidence = 0.85 if ent.label_ in ['PERSON', 'ORG'] else 0.75
                
                entities.append(Entity(
                    type=type_mapping[ent.label_],
                    value=ent.text,
                    confidence=confidence,
                    confidence_level=get_confidence_level(confidence),
                    context=text[max(0, ent.start_char - 30):min(len(text), ent.end_char + 30)]
                ))
    except Exception as e:
        logger.error(f"NLP extraction error: {e}")
    
    return entities

def extract_fields(entities: List[Entity]) -> Dict[str, ExtractedField]:
    """Extract key-value fields from entities"""
    fields = {}
    
    by_type = {}
    for e in entities:
        if e.type not in by_type:
            by_type[e.type] = []
        by_type[e.type].append(e)
    
    # Extract best entity of each type as a field
    field_mapping = {
        'date': 'date',
        'amount': 'total_amount',
        'email': 'email',
        'phone': 'phone',
        'invoice': 'invoice_number',
        'person': 'person_name',
        'organization': 'organization'
    }
    
    for entity_type, field_name in field_mapping.items():
        if entity_type in by_type:
            best = max(by_type[entity_type], key=lambda e: e.confidence)
            fields[field_name] = ExtractedField(
                field_name=field_name,
                value=best.value,
                confidence=best.confidence,
                confidence_level=best.confidence_level,
                extraction_method='regex' if entity_type in ['email', 'phone', 'date', 'amount'] else 'nlp'
            )
    
    return fields

# ============================================================================
# Document Processor
# ============================================================================

async def process_document(
    file_content: bytes,
    filename: str,
    min_confidence: float = 0.5
) -> ExtractionResult:
    """Main document processing function"""
    start_time = time.time()
    document_id = str(uuid.uuid4())[:8]
    
    logger.info(f"[{document_id}] Processing: {filename}")
    
    try:
        # Determine file type
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        is_pdf = ext == 'pdf'
        
        # OCR Extraction
        if is_pdf:
            page_results = extract_text_from_pdf(file_content)
            pages = [
                PageResult(
                    page_number=i+1,
                    text=text,
                    confidence=conf,
                    word_count=len(text.split())
                )
                for i, (text, conf) in enumerate(page_results)
            ]
        else:
            image = Image.open(io.BytesIO(file_content))
            text, conf = extract_text_from_image(image)
            pages = [PageResult(
                page_number=1,
                text=text,
                confidence=conf,
                word_count=len(text.split())
            )]
        
        full_text = ' '.join([p.text for p in pages])
        avg_ocr_conf = sum([p.confidence for p in pages]) / len(pages) if pages else 0
        
        logger.info(f"[{document_id}] OCR complete: {len(pages)} pages, confidence: {avg_ocr_conf:.2f}")
        
        # Entity Extraction
        regex_entities = extract_regex_entities(full_text)
        nlp_entities = extract_nlp_entities(full_text)
        all_entities = regex_entities + nlp_entities
        
        # Remove duplicates
        seen = set()
        unique_entities = []
        for e in all_entities:
            key = (e.type, e.value.lower())
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        # Filter by confidence
        unique_entities = [e for e in unique_entities if e.confidence >= min_confidence]
        
        logger.info(f"[{document_id}] Extracted {len(unique_entities)} entities")
        
        # Extract fields
        fields = extract_fields(unique_entities)
        
        # Calculate overall confidence
        if unique_entities:
            entity_conf = sum(e.confidence for e in unique_entities) / len(unique_entities)
        else:
            entity_conf = 0.5
        
        if fields:
            field_conf = sum(f.confidence for f in fields.values()) / len(fields)
        else:
            field_conf = 0.5
        
        overall_conf = (avg_ocr_conf * 0.4) + (entity_conf * 0.3) + (field_conf * 0.3)
        
        processing_time = time.time() - start_time
        
        metadata = ProcessingMetadata(
            filename=filename,
            file_type='pdf' if is_pdf else 'image',
            file_size_bytes=len(file_content),
            processing_time_seconds=round(processing_time, 2),
            pages_processed=len(pages),
            ocr_engine='tesseract',
            extraction_methods=['ocr_tesseract', 'regex'] + (['nlp_spacy'] if nlp else []),
            timestamp=datetime.utcnow().isoformat(),
            warnings=[]
        )
        
        logger.info(f"[{document_id}] Processing complete in {processing_time:.2f}s")
        
        return ExtractionResult(
            success=True,
            document_id=document_id,
            filename=filename,
            text=full_text,
            pages=pages,
            entities=unique_entities,
            fields=fields,
            overall_confidence=round(overall_conf, 3),
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"[{document_id}] Processing error: {e}")
        return ExtractionResult(
            success=False,
            document_id=document_id,
            filename=filename,
            text="",
            pages=[],
            entities=[],
            fields={},
            overall_confidence=0.0,
            metadata=ProcessingMetadata(
                filename=filename,
                file_type='unknown',
                file_size_bytes=len(file_content),
                processing_time_seconds=time.time() - start_time,
                pages_processed=0,
                ocr_engine='tesseract',
                extraction_methods=[],
                timestamp=datetime.utcnow().isoformat(),
                warnings=[str(e)]
            ),
            error_message=str(e)
        )

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Document Information Extraction API",
    description="Extract structured information from PDFs and images",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "healthy", "message": "Document Extraction API is running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "ocr": "tesseract", "nlp": "available" if nlp else "unavailable"}

@app.post("/extract", response_model=ExtractionResult)
async def extract(
    file: UploadFile = File(...),
    min_confidence: float = Form(0.5)
):
    """Extract information from uploaded document"""
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    allowed = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}
    ext = os.path.splitext(file.filename.lower())[1]
    
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported format. Allowed: {allowed}")
    
    try:
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        if len(content) > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")
        
        result = await process_document(content, file.filename, min_confidence)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/supported-entities")
async def supported_entities():
    """Get list of supported entity types"""
    return {
        "entities": [
            {"type": "person", "description": "Person names"},
            {"type": "organization", "description": "Company/organization names"},
            {"type": "date", "description": "Dates"},
            {"type": "amount", "description": "Monetary amounts"},
            {"type": "email", "description": "Email addresses"},
            {"type": "phone", "description": "Phone numbers"},
            {"type": "invoice", "description": "Invoice numbers"},
            {"type": "percentage", "description": "Percentages"},
            {"type": "url", "description": "URLs"},
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)