# Architecture decisions

## Frontend and API separation
The React/Vite single-page frontend communicates with FastAPI through the configured `VITE_API_BASE_URL`. The API remains authoritative for validation, permissions and data access.

## Authentication
Short-lived bearer access tokens are kept in browser session storage. Refresh tokens are opaque, hashed at rest, rotated on use and carried in an HttpOnly cookie. Both production services use sibling subdomains of `vercel.app`; the cookie uses Secure and SameSite=Lax, and requests include credentials. CORS is restricted to the configured frontend origin.

## Live summary
The public summary is cache-validated with ETag and 304 responses. The frontend pauses polling while the document is hidden and backs off after failures.

## Explainability
Deterministic scoring is the source of rankings. Gemini is an optional explanation layer; rules-based explanation remains the fallback.

## Synthetic data
Demo records are explicitly marked synthetic. Purge filters only synthetic records and requires administrator authorization plus explicit confirmation in the UI.

## Agronomic safety
Scores are suitability heuristics and the UI repeats the advisory disclaimer near recommendations and print output.
