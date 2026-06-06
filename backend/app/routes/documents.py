# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services.dependencies import get_current_user

router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)

@router.get("/")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    # Depends(get_current_user) means:
    # "Before running this function, run get_current_user first"
    # "If it fails (invalid token), return 401 automatically"
    # "If it succeeds, pass the User object here as current_user"
):
    """
    List all documents for the logged-in user.
    Requires authentication.
    """
    return {
        "documents": [],
        "total": 0,
        "owner": current_user.email
        # Now we know WHO is asking!
    }

@router.get("/{document_id}")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return {
        "id": document_id,
        "name": f"document_{document_id}.pdf",
        "status": "processed",
        "owner": current_user.email
    }

@router.post("/")
def upload_document(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return {
        "message": "Document upload coming in Week 3!",
        "owner": current_user.email
    }