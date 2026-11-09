# DocuMind API image. Built by docker-compose.yml (service "api"), or by hand:
#   docker build -t documind-api backend
# Secrets (SECRET_KEY, LLM keys) are never built in: they come from the
# environment when the container starts.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

# Dependencies first, so a code change does not reinstall them. CPU-only
# torch: the default Linux build also installs NVIDIA's CUDA libraries.
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Download the embedding model now, so the container starts without network
# access and the first upload does not wait for a download. Must match
# MODEL_NAME in app/services/embedding_service.py (a test checks this).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# From here on, never contact the Hugging Face hub: use the files above.
ENV HF_HUB_OFFLINE=1

COPY app ./app

# Run as an unprivileged user. uploads/ must be writable by it; a named
# volume mounted there starts with this ownership.
RUN useradd --create-home --uid 1000 documind \
    && mkdir -p /app/uploads \
    && chown documind:documind /app/uploads
USER documind

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
