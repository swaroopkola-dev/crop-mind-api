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

The `.env.example` file defines exactly these configuration keys:

- `MONGODB_URI`: MongoDB connection URI.
- `DB_NAME`: MongoDB database name.
- `JWT_SECRET`: signing secret of at least 32 characters in production.
- `JWT_ALGORITHM`: currently supports `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: access-token lifetime in minutes.
- `REFRESH_TOKEN_EXPIRE_DAYS`: refresh-token lifetime in days.
- `GEMINI_API_KEY`: optional server-side Gemini API key.
- `GEMINI_MODEL`: Gemini model identifier.
- `GEMINI_TIMEOUT_SECONDS`: Gemini explanation timeout.
- `FRONTEND_ORIGIN`: exact frontend origin allowed by CORS.
- `CRON_SECRET`: optional secret reserved for authenticated scheduled jobs.
- `SIMULATOR_ENABLED`: simulator feature toggle.
- `ADMIN_SEED_EMAIL`: initial administrator email for seed setup.
- `ADMIN_SEED_PASSWORD`: initial administrator password for seed setup.
- `SEED_TOKEN`: secret for the protected seed endpoint.
- `ENVIRONMENT`: such as `development` or `production`.
- `LOG_LEVEL`: Python log level, for example `INFO`.

Use Vercel environment variables for deployment secrets. Do not commit `.env` or paste secret values into issue trackers.

## API

Routes are prefixed `/api`. Open `/docs` for the API schema. Health is `/api/health`.

## Data and limitations

Seed crop ranges are approximate educational data. They are not verified crop advisories and do not guarantee yield or crop success. Token expiration is checked in application code independently of TTL cleanup.
