# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import documents, query, auth
import app.models.user      # Must import so SQLAlchemy knows about these models
import app.models.document   # before calling create_all()

# Create all database tables automatically
# SQLAlchemy reads all models that inherited from Base
# and creates their tables in PostgreSQL if they don't exist
# This is safe to run every time — it skips tables that already exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DocuMind API",
    description="AI-powered document intelligence platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(query.router)

@app.get("/")
def root():
    return {
        "message": "Welcome to DocuMind API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}