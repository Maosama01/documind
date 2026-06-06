from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.schemas.token import TokenData
from app.config import settings

# CryptContext sets up bcrypt for password hashing
# bcrypt is an industry-standard hashing algorithm
# "deprecated='auto'" means old/weak hashes are auto-upgraded
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─────────────────────────────────────────
# PASSWORD FUNCTIONS
# ─────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """
    Takes a plain text password and returns a bcrypt hash.
    Example:
      Input:  "mypassword123"
      Output: "$2b$12$EixZaYVK1fsbw1Zfb..." (60 character hash)
    """
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks if a plain password matches a stored hash.
    Used during login to verify the user's password.
    Returns True if match, False if wrong password.
    """
    return pwd_context.verify(plain_password, hashed_password)

# ─────────────────────────────────────────
# JWT TOKEN FUNCTIONS
# ─────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT token containing the given data.
    
    The token encodes:
    - The data (e.g., {"sub": "user@email.com"})
    - An expiration time
    
    It's signed with SECRET_KEY so we can verify it wasn't tampered with.
    """
    to_encode = data.copy()
    
    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    # "exp" is a standard JWT claim meaning "expiration"
    to_encode.update({"exp": expire})
    
    # jwt.encode creates the token string
    # settings.SECRET_KEY is our signing key
    # settings.ALGORITHM is "HS256" — the signing algorithm
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def verify_token(token: str) -> Optional[TokenData]:
    """
    Validates a JWT token and extracts the user's email from it.
    Returns None if token is invalid or expired.
    """
    try:
        # jwt.decode verifies the signature and expiration
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        # "sub" is a standard JWT claim meaning "subject" (the user)
        email: str = payload.get("sub")
        if email is None:
            return None
        return TokenData(email=email)
    except JWTError:
        # Token is invalid, expired, or tampered with
        return None

# ─────────────────────────────────────────
# DATABASE USER FUNCTIONS
# ─────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Fetch a user from database by their email address."""
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Create a new user in the database.
    Hashes the password before storing.
    """
    # Hash the password — never store plain text!
    hashed = hash_password(user_data.password)
    
    # Create the SQLAlchemy User object
    db_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed
    )
    
    # Add to database session
    db.add(db_user)
    
    # Commit saves the changes to the actual database
    db.commit()
    
    # Refresh loads the new data back (e.g., the auto-generated id)
    db.refresh(db_user)
    
    return db_user

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Verify email + password combination.
    Returns the User if valid, None if invalid.
    Used during login.
    """
    user = get_user_by_email(db, email)
    
    if not user:
        return None    # User doesn't exist
    
    if not verify_password(password, user.hashed_password):
        return None    # Wrong password
    
    return user        # Valid credentials