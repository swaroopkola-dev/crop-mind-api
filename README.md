# CropMind API

FastAPI backend for the CropMind educational crop recommendation prototype.

## Current implementation

- Deterministic, explainable crop scoring and ranking.
- Crop CRUD and initial educational crop profile seed data.
- Account registration/login, short-lived JWT access tokens and rotating opaque refresh cookies.
- Recommendation creation, optional account history, comparison, and fallback-first Gemini explanations.
- Admin routes, audit events, health endpoint, and ETag-backed summary polling.
- Vercel Python entrypoint.

**Agronomic disclaimer:** seed profile ranges are approximate educational data, not validated farming advice. Scores are suitability heuristics, not probabilities or yield estimates.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Set MONGODB_URI to a database you are authorized to use.
uvicorn app.main:app --reload
```

Seed only when intentionally targeting a database you control:

```bash
python -m scripts.seed
```

Set `ADMIN_SEED_EMAIL` and `ADMIN_SEED_PASSWORD` to create the first admin. Never commit `.env` or credentials.

## Tests

```bash
pytest
ruff check .
```

Tests use fake crop profiles and do not require a live database. For integration tests, configure a separate test database and never point destructive tests at production.

## Environment variables

See `.env.example`. Production requires a strong `JWT_SECRET`, secure cookies, a specific CORS origin list, and production environment configuration. Keep `MONGODB_URI` and `GEMINI_API_KEY` on the server only.

## API

Routes are prefixed `/api`. Open `/docs` in development. Health is `/api/health`.

Some broader Phase 1 administrative ideas (background simulator generation, full operational analytics, and deployed-runtime validation) remain in progress and are not claimed as complete merely because route shells exist.

## Atlas setup note

`scripts/seed.py` creates indexes with TTL options using the official PyMongo driver. The Atlas connector used during initial provisioning cannot set `expireAfterSeconds`, so named expiry indexes created through that connector are not guaranteed to have TTL behavior until `scripts/seed.py` runs with the configured `MONGODB_URI`. Token expiry is always checked in application code and does not depend on TTL cleanup.
