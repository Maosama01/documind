from typing import Annotated, List, Optional

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, StringConstraints
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.dependencies import get_current_user
from app.services.document_service import get_document_by_id, semantic_search
from app.services.llm_service import LLMProviderError, generate_answer

router = APIRouter(
    prefix="/query",
    tags=["query"]
)


class QueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    document_id: int
    max_results: int = Field(default=5, ge=1, le=10)
    # How many chunks to retrieve and give to the answer generator


class SourceResponse(BaseModel):
    rank: int  # 1 = most similar to the question
    page_number: Optional[int]
    chunk_index: int
    content: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    cited_pages: List[int]
    grounded: bool
    provider: str
    sources: List[SourceResponse]


@router.post("/", response_model=QueryResponse)
def query_document(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Answer a question about one of your processed documents.

    1. Retrieves the max_results chunks most similar to the question (pgvector).
    2. Asks the configured provider (LLM_PROVIDER: gemini, anthropic, or none)
       to answer from those chunks only, citing pages as [p.N]. With "none",
       the answer is the document's most similar sentences, labelled as such.
    3. Returns "Not found in the document." when the sources do not hold the answer.

    grounded is true when the answer cites at least one page and every cited
    page is among the retrieved sources, or when the answer is "Not found in
    the document.". It checks page numbers only, not whether the cited text
    supports the answer.

    Errors: 404 if the document does not exist or is not yours, 400 if it is
    not processed yet, 502 if the LLM provider fails.
    """
    document = get_document_by_id(db, request.document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.status != "processed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not ready yet. Status: {document.status}"
        )

    chunks = semantic_search(db, request.question, request.document_id, request.max_results)

    try:
        result = generate_answer(request.question, chunks)
    except LLMProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Answer generation failed: {error}"
        )

    return {
        "question": request.question,
        "answer": result.answer,
        "cited_pages": result.cited_pages,
        "grounded": result.grounded,
        "provider": result.provider,
        "sources": [
            {
                "rank": rank,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            }
            for rank, chunk in enumerate(chunks, start=1)
        ],
    }
