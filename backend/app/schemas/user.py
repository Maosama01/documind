# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

# BaseModel from pydantic automatically validates data
# If a field is wrong type, pydantic raises a clear error

class UserCreate(BaseModel):
    """What the client sends when signing up"""
    email: EmailStr          # EmailStr validates it's a real email format
    full_name: str
    password: str            # Plain text — we'll hash it in the service

class UserLogin(BaseModel):
    """What the client sends when logging in"""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """What we send BACK to the client — notice: NO password field!"""
    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
        # This tells Pydantic: "you can create this from a SQLAlchemy model object"
        # Without this, Pydantic can only read plain dicts, not ORM objects

class UserUpdate(BaseModel):
    """What the client sends when updating their profile"""
    full_name: Optional[str] = None
    password: Optional[str] = None
    # Optional means the field isn't required
    # = None means default value is None if not provided