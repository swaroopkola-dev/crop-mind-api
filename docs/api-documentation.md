# API documentation

Base path: `/api`. Interactive OpenAPI docs are enabled in non-production environments at `/docs`.

- `GET /health`: minimal health and database ping.
- `POST /auth/register`: register normal account (never admin).
- `POST /auth/login`: access token and HttpOnly refresh cookie.
- `POST /auth/refresh`: rotate refresh cookie and renew access token.
- `POST /auth/logout`: revoke current refresh token and clear cookie.
- `GET /auth/me`: current user profile.
- `POST /auth/change-password`: change password and revoke refresh sessions.
- `POST /recommendations`: rank active crops and persist output.
- `GET /recommendations`: current user's recommendation history.
- `POST /compare`: compare two to four active crop profiles.
- `GET /crops`: list active crops.
- `GET /crops/{id}`: view an active crop profile.
- Crop mutations require an administrator.
- `/admin/*`: protected administrator endpoints for overview, users, recommendations, audit, settings, simulator controls and CSV export.
- `GET /live/summary`: small dashboard summary with ETag conditional responses.
- `GET /live/activity`: administrator activity cursor.

Error responses contain `detail`, `code`, and `request_id`. The backend verifies authorization independently of frontend routing.
