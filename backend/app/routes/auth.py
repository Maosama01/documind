# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.security import OAuth2PasswordRequestForm
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.token import Token
from app.services.auth_service import (
    create_user,
    get_user_by_email,
    authenticate_user,
    create_access_token
)
from app.services.dependencies import get_current_user
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

def issue_token(db: Session, email: str, password: str) -> dict:
    """
    Check the credentials and return a JWT access token.
    Shared by /auth/login (JSON) and /auth/token (form).
    """
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},   # "sub" = subject = the user's identity
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password (JSON body: {"email", "password"}).

    - Verifies credentials
    - Returns a JWT access token

    The client stores this token and sends it with every future request
    in the header: "Authorization: Bearer <token>"
    """
    return issue_token(db, user_data.email, user_data.password)

@router.post("/token", response_model=Token)
def login_with_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with the OAuth2 password form: form fields "username" and "password".

    Same as /auth/login, but in the format Swagger's Authorize button sends
    (the OAuth2 "password" flow names the field "username"). Put your email
    in the username field.
    """
    return issue_token(db, form_data.username, form_data.password)

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get the currently logged-in user's information.
    Requires a valid JWT token.
    """
    return current_user