import os
import aiofiles
# pyrefly: ignore [missing-import]
from pypdf import PdfReader
from typing import List, Dict
from fastapi import UploadFile

# Local uploads folder — temporary storage before we add S3
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
# exist_ok=True means: create the folder if it doesn't exist,
# but don't raise an error if it already exists

async def save_upload_file(upload_file: UploadFile, filename: str) -> str:
    """
    Save an uploaded file to the local uploads folder.
    Returns the file path where it was saved.
    
    'async' means this function doesn't block the server while saving.
    Other requests can be processed while the file is being written.
    """
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # aiofiles handles file I/O asynchronously
    async with aiofiles.open(file_path, "wb") as buffer:
        content = await upload_file.read()
        await buffer.write(content)
    
    return file_path

def extract_text_from_pdf(file_path: str) -> List[Dict]:
    """
    Extract text from every page of a PDF.
    Returns a list of dicts, one per page:
    [
        {"page_number": 1, "text": "Page 1 content..."},
        {"page_number": 2, "text": "Page 2 content..."},
        ...
    ]
    """
    pages = []
    
    reader = PdfReader(file_path)
    # PdfReader opens the PDF and reads its structure
    
    for page_num, page in enumerate(reader.pages, start=1):
        # enumerate starts counting from 1 (human-readable page numbers)
        
        text = page.extract_text()
        # extract_text() reads all text content from a page
        
        if text and text.strip():
            # Only include pages that have actual text
            # .strip() removes leading/trailing whitespace
            pages.append({
                "page_number": page_num,
                "text": text.strip()
            })
    
    return pages

def get_pdf_metadata(file_path: str) -> Dict:
    """
    Extract basic metadata from a PDF.
    Returns page count and a preview of the first page.
    """
    reader = PdfReader(file_path)
    
    page_count = len(reader.pages)
    
    # Get preview from first page (first 500 characters)
    preview = ""
    if reader.pages:
        first_page_text = reader.pages[0].extract_text()
        if first_page_text:
            preview = first_page_text[:500]
    
    return {
        "page_count": page_count,
        "content_preview": preview
    }

def get_file_size(file_path: str) -> int:
    """Returns file size in bytes"""
    return os.path.getsize(file_path)