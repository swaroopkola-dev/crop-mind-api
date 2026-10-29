# CropMind API

FastAPI backend for the CropMind educational crop recommendation prototype.

## Current implementation

- Deterministic, explainable crop scoring and ranking.
- Crop CRUD and initial educational crop profile seed data.
- Account registration/login, short-lived JWT access tokens and rotating opaque refresh cookies.
- Recommendation creation, optional account history, comparison, and fallback-first Gemini explanations.
- Admin routes, audit events, health endpoint, and ETag-backed summary polling.
- FastAPI application entrypoint at `api/index.py`.

**Agronomic disclaimer:** seed profile ranges are approximate educational data, not validated farming advice. Scores are suitability heuristics, not probabilities or yield estimates.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Seed only when intentionally targeting a database you control:

```bash
python -m scripts.seed
```

The seed command reads `MONGODB_URI`, `DB_NAME`, `ADMIN_SEED_EMAIL`, and `ADMIN_SEED_PASSWORD`. Never commit `.env` or credentials.

## Tests

```bash
pytest
ruff check .
```

Tests use fake crop profiles and do not require a live database. For integration tests, use a separate test database and never point destructive tests at production.

## Environment variables

The `.env.example` file contains the complete environment contract. The application uses only these keys:

- `MONGODB_URI`: MongoDB connection URI.
- `DB_NAME`: database name (default example: `cropmind`).
- `JWT_SECRET`: high-entropy signing secret; at least 32 characters in production.
- `JWT_ALGORITHM`: `HS256` for this implementation.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: access token lifetime in minutes.
- `REFRESH_TOKEN_EXPIRE_DAYS`: refresh token lifetime in days.
- `GEMINI_API_KEY`: optional server-side Gemini API key.
- `GEMINI_MODEL`: model identifier, default example `gemini-3.8-flash`.
- `GEMINI_TIMEOUT_SECONDS`: request timeout for Gemini explanation.
- `FRONTEND_ORIGIN`: exact frontend origin allowed by CORS.
- `CRON_SECRET`: optional secret reserved for authenticated scheduled jobs.
- `SIMULATOR_ENABLED`: whether synthetic simulator functionality is enabled.
- `ADMIN_SEED_EMAIL`: optional initial administrator email for the seed operation.
- `ADMIN_SEED_PASSWORD`: optional initial administrator password for the seed operation.
- `SEED_TOKEN`: secret used to authorize the protected admin seed route.
- `ENVIRONMENT`: environment such as `development` or `production`.
- `LOG_LEVEL`: Python logging level (for example, `INFO`).

Keep secrets in the hosting provider's secret environment-variable store; never commit their values.

## API

Routes are prefixed `/api`. Open `/docs` in development. Health is `/api/health`.

## Atlas setup note

`scripts/seed.py` creates indexes with TTL options using PyMongo. Token expiry is also checked in application code and does not depend on TTL cleanup.
