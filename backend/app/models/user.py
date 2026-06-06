# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, Boolean, DateTime
# pyrefly: ignore [missing-import]
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    # __tablename__ tells SQLAlchemy what to name the table in PostgreSQL
    __tablename__ = "users"
    
    # Each Column() creates a column in the table
    # The first argument is the data type
    
    id = Column(Integer, primary_key=True, index=True)
    # primary_key=True → this is the unique identifier for each row
    # index=True → creates a database index for faster lookups
    
    email = Column(String, unique=True, index=True, nullable=False)
    # unique=True → no two users can have the same email
    # nullable=False → this field is required, cannot be empty
    
    full_name = Column(String, nullable=False)
    
    hashed_password = Column(String, nullable=False)
    # We NEVER store the real password
    # Only the bcrypt hash of the password
    
    is_active = Column(Boolean, default=True)
    # Allows disabling accounts without deleting them
    
    is_verified = Column(Boolean, default=False)
    # For email verification (we'll add this later)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # server_default=func.now() → PostgreSQL automatically sets
    # this to the current timestamp when a row is created
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # onupdate=func.now() → automatically updates when row changes
    
    def __repr__(self):
        # This controls what prints when you do print(user)
        # Helpful for debugging
        return f"<User id={self.id} email={self.email}>"