# pyrefly: ignore [missing-import]
from fastapi import APIRouter

router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)

@router.get("/")
def list_documents():
    return {
        "documents": [
            {"id": 1, "name": "sample.pdf", "status": "processed"},
            {"id": 2, "name": "contract.pdf", "status": "processing"}
        ],
        "total": 2
    }

@router.get("/{document_id}")
def get_document(document_id: int):
    return {
        "id": document_id,
        "name": f"document_{document_id}.pdf",
        "status": "processed",
        "pages": 10
    }

@router.post("/")
def upload_document():
    return {
        "message": "Document uploaded successfully",
        "id": 3,
        "status": "processing"
    }