"""
Write the API's OpenAPI schema to frontend/openapi.json.

    cd backend && .venv/bin/python -m scripts.export_openapi

The frontend generates its TypeScript types from that file
(`npm run api:types`), so a change to a route or a schema shows up as a type
error in the frontend. CI runs this and fails if the committed copy differs.
Needs SECRET_KEY like any import of the app; no database or model is used.
"""
import json
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> int:
    from app.main import app

    OUTPUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
