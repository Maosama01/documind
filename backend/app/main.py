from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routes import documents, query, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts, before it accepts requests:
    # creates the pgvector extension, then any missing tables.
    # It used to run at import time, which meant nothing (including tests)
    # could import this module without a live database.
    init_db()
    yield


app = FastAPI(
    title="DocuMind API",
    description="AI-powered document intelligence platform",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan
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
