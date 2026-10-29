# CropMind API architecture

The FastAPI application is split into routers, Pydantic schemas, services, MongoDB access and security dependencies. The deterministic scoring service is authoritative. Gemini only formats a prose explanation from structured computed results and falls back to templates if unavailable.

## Persistence

MongoDB collections: users, crops, recommendations, refresh_tokens, activity_logs, settings, login_attempts, comparisons. Index setup is idempotent. Seed profiles are explicitly tagged `source=seed` and `is_synthetic=true` to avoid confusing prototype data with verified/live crop data.

## Security

Passwords are hashed. Public registration creates only the user role. JWT access token validation checks signature, issuer, expiry and token type, and protected routes reread active user status from MongoDB. Refresh tokens are random opaque values; only SHA-256 digests are persisted and used for rotation/revocation. Never commit secrets.

## Deployment

Vercel Python entrypoint: `api/index.py`, importing `app.main:app`. The serverless target must be smoke-tested against the pinned dependencies and configured MongoDB network allowlist before production use.
