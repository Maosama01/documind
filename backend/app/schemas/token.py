# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    """The JWT token response after successful login"""
    access_token: str
    token_type: str    # Always "bearer" — this is the standard

class TokenData(BaseModel):
    """Data stored INSIDE the JWT token"""
    email: Optional[str] = None
    # When we verify a token, we extract this data
    # to know which user is making the request