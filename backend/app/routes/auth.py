# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.schemas.user import UserCreate, UserResponse
from app.schemas.token import Token
from app.services.auth_service import (
    create_user,
    get_user_by_email,
    authenticate_user,
    create_access_token
)
from app.config import settings

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.
    
    - Checks if email already exists
    - Hashes the password
    - Saves user to database
    - Returns user info (WITHOUT password)
    
    status_code=201 means "Created" — more accurate than 200 for creation
    response_model=UserResponse tells FastAPI to filter the output
    through UserResponse schema (so hashed_password never leaks out)
    """
    
    # Check if user already exists
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )
    
    # Create the user
    user = create_user(db, user_data)
    return user

@router.post("/login", response_model=Token)
def login(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    - Verifies credentials
    - Returns a JWT access token
    
    The client stores this token and sends it with every future request
    in the header: "Authorization: Bearer <token>"
    """
    
    # Verify credentials
    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},   # "sub" = subject = the user's identity
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    db: Session = Depends(get_db),
    token: str = Depends(__import__('fastapi').security.OAuth2PasswordBearer(tokenUrl="/auth/login"))
):
    """
    Get the currently logged-in user's information.
    Requires a valid JWT token.
    """
    from app.services.dependencies import get_current_user
    from app.services.auth_service import verify_token, get_user_by_email
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_email(db, token_data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user