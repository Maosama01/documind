# pyrefly: ignore [missing-import]
from fastapi import Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.security import OAuth2PasswordBearer
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import verify_token, get_user_by_email
from app.models.user import User

# OAuth2PasswordBearer tells FastAPI:
# "Look for a Bearer token in the Authorization header"
# tokenUrl="/auth/login" tells the Swagger docs where to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that extracts and validates the current user
    from the JWT token in the request header.
    
    Usage: add "current_user: User = Depends(get_current_user)"
    to any route that requires authentication.
    
    FastAPI automatically:
    1. Extracts the token from the Authorization header
    2. Calls this function
    3. Passes the result to your route
    4. Returns 401 error if token is invalid
    """
    
    # This exception is returned if authentication fails
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
        # WWW-Authenticate header is required by the OAuth2 standard
    )
    
    # Validate the token
    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception
    
    # Get the actual user from database
    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )
    
    return user