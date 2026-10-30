# CropMind API documentation

Base URL: `https://crop-mind-api.vercel.app/api`  
Interactive schema: `https://crop-mind-api.vercel.app/docs`

## Health
`GET /health` — returns application and database health. A healthy response is HTTP 200 with `status=ok` and `database=ok`.

## Authentication
- `POST /auth/register`: body `{email,password,display_name?}`; creates a user.
- `POST /auth/login`: body `{email,password}`; returns `access_token` and sets rotating HttpOnly refresh cookie.
- `POST /auth/refresh`: rotates refresh cookie and returns a new access token.
- `POST /auth/logout`: revokes current refresh token and clears cookie (204).
- `GET /auth/me`: current user; bearer token required.
- `POST /auth/change-password`: body `{current_password,new_password}`; current access token required.

## Recommendations and comparison
- `POST /recommendations`: required `soil_type`, `ph`, `rainfall_mm`, `temperature_c`, `humidity_pct`, `season`; optional N/P/K. Returns ranked results, missing optional inputs, explanation source and disclaimer. Requires active crop profiles.
- `GET /recommendations`: authenticated user's saved history.
- `GET /recommendations/{id}`: owner or administrator.
- `DELETE /recommendations/{id}`: owner or administrator.
- `POST /recommendations/{id}/save`: attach an anonymous recommendation to the signed-in user.
- `POST /compare`: 2–4 active crop IDs and a validated field input object.

## Crop profiles
- `GET /crops` and `GET /crops/{id}`: active public profiles.
- `POST /crops`, `PUT /crops/{id}`, `DELETE /crops/{id}`: administrator-only create, replace and deactivate.

## Live endpoints
- `GET /live/summary`: public summary with `ETag`. Send `If-None-Match` to receive 304 when unchanged.
- `GET /live/activity`: administrator-only activity feed.

## Administrator endpoints
All require a bearer token for an active administrator:
- `POST /admin/seed`: protected separately by `X-Seed-Token`; does not require an admin login.
- `GET /admin/overview`
- `GET /admin/users`, `GET /admin/users/{id}`, `PATCH /admin/users/{id}`, `DELETE /admin/users/{id}`, `POST /admin/users/{id}/revoke-sessions`
- `GET /admin/recommendations`, `GET /admin/recommendations/{id}`, `DELETE /admin/recommendations/{id}`
- `GET /admin/activity`, `GET /admin/system`
- `GET /admin/settings`, `PUT /admin/settings`
- `POST /admin/simulator/toggle?enabled=true|false`, `POST /admin/simulator/tick`, `POST /admin/synthetic/purge`
- `GET /admin/export/users.csv`, `GET /admin/export/recommendations.csv`, `GET /admin/export/activity.csv`

## Errors and security
Validation errors return 422; unauthenticated calls return 401; authenticated non-admin calls return 403; missing records return 404; duplicate records return 409. Never expose credentials, tokens or password hashes in responses or logs.
