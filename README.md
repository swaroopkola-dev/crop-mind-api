# CropMind API

## 1. API overview
FastAPI service for explainable crop suitability recommendations, account sessions, crop profiles, comparisons, live summaries and administrator operations.

## 2. Live applications
- Frontend: https://crop-mind-rouge.vercel.app
- API: https://crop-mind-api.vercel.app
- OpenAPI UI: https://crop-mind-api.vercel.app/docs
- Health: https://crop-mind-api.vercel.app/api/health

## 3. Architecture
The Vercel Python function imports `api/index.py`, which exposes the FastAPI application in `app/main.py`. Routers depend on shared authentication, database and repository helpers. MongoDB Atlas stores accounts, sessions, crop profiles, recommendations, comparisons, settings and audit events.

## 4. Technology stack
Python 3.12, FastAPI, Pydantic, PyMongo, MongoDB Atlas, JWT access tokens, rotating opaque refresh tokens, optional Gemini explanations, Vercel Functions and GitHub Actions.

## 5. API base and documentation
All application routes are prefixed with `/api`. Interactive API documentation is available at the live `/docs` URL. Health is `GET /api/health`.

## 6. Endpoint inventory
- Health: `GET /api/health`.
- Auth: `POST /api/auth/register`, `login`, `refresh`, `logout`, `change-password`; `GET /api/auth/me`.
- Recommendations: `POST /api/recommendations`; `GET /api/recommendations`, `GET /api/recommendations/{id}`, `DELETE /api/recommendations/{id}`, `POST /api/recommendations/{id}/save`.
- Comparison: `POST /api/compare`.
- Crops: `GET /api/crops`, `GET /api/crops/{id}`, `POST /api/crops`, `PUT /api/crops/{id}`, `DELETE /api/crops/{id}`.
- Live: `GET /api/live/summary` (ETag/304), `GET /api/live/activity` (admin).
- Admin: `/api/admin/seed`, `overview`, `users`, `recommendations`, `activity`, `system`, `settings`, `simulator/tick`, `simulator/toggle`, `synthetic/purge`, and CSV export routes. See [API documentation](docs/api-documentation.md) for methods and access rules.

## 7. Authentication and sessions
Registration and login issue short-lived bearer access tokens. Login and refresh set an HttpOnly, Secure-in-production, SameSite=Lax rotating refresh cookie scoped to `/api/auth`. Refresh tokens are stored hashed and rotated on refresh. Admin routes enforce the admin role server-side and return 403 for non-admin accounts.

## 8. Database design
MongoDB database `cropmind` uses collections for crops, users, refresh_tokens, recommendations, comparisons, settings, activity_logs and login_attempts. See [database design](docs/database-design.md).

## 9. Recommendation engine
The deterministic scoring service evaluates soil type, pH, nitrogen, phosphorus, potassium, rainfall, temperature, humidity and season. Input ranges are validated by Pydantic. Scores are relative suitability heuristics, not yield predictions or probabilities.

## 10. Explanation provider
Gemini is optional. If it is unavailable or times out, the service returns a rules-based explanation and records the source as `fallback`; Gemini explanations are marked `gemini`. Never expose the server-side API key.

## 11. Administrator operations
Admin-only endpoints manage users and sessions, inspect recommendations and activity, manage supported settings, inspect system status, operate the simulator, purge synthetic records and export CSV. User deletion prevents self-deletion and deletion of the last active administrator, revokes sessions and removes account ownership from retained recommendation aggregates.

## 12. Seed workflow
The protected seed route is `POST /api/admin/seed` with header `X-Seed-Token: <SEED_TOKEN>`. It upserts the 15 educational crop profiles, creates the administrator from `ADMIN_SEED_EMAIL` and `ADMIN_SEED_PASSWORD` when absent, ensures indexes and inserts supported default settings only when missing. The route has not been run as part of this build. Never commit or publish seed credentials.

## 13. Environment variables
The configured backend keys are: `MONGODB_URI`, `DB_NAME`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS`, `FRONTEND_ORIGIN`, `CRON_SECRET`, `SIMULATOR_ENABLED`, `ADMIN_SEED_EMAIL`, `ADMIN_SEED_PASSWORD`, `SEED_TOKEN`, `ENVIRONMENT`, `LOG_LEVEL`. Values belong only in Vercel environment settings.

## 14. Local development
Use Python 3.12+, install `requirements.txt`, configure a private development `.env`, then run `uvicorn app.main:app --reload`. Never point local tests at production data.

## 15. Testing and CI
GitHub Actions runs lint and backend tests on changes. Keep tests isolated from production MongoDB. Smoke tests are documented in the project release checklist; destructive simulator and purge endpoints require explicit administrator confirmation.

## 16. Deployment and demo-only credentials
Production is connected to the GitHub `main` branch and deployed on Vercel. No shared demo username or password is published. Configure a dedicated demo administrator privately through the seed environment variables and protected seed request; do not use production credentials as demo credentials.

## 17. Limitations and advisory disclaimer
Seed profiles are approximate educational examples and have not been validated for every region. Suitability scores are comparative heuristics, not guarantees, yield estimates or probabilities. Consult current soil tests and qualified local agronomists before making agricultural decisions.
