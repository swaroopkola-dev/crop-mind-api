# CropMind integration map

```text
Browser (crop-mind)
  ├─ VITE_API_BASE_URL
  ├─ bearer access token
  └─ credentials: include
       │ HTTPS + CORS (FRONTEND_ORIGIN)
       ▼
Vercel FastAPI (crop-mind-api)
  ├─ /api/auth ── users + refresh_tokens
  ├─ /api/recommendations ── crops + recommendations + activity_logs
  ├─ /api/compare ── crops + comparisons + activity_logs
  ├─ /api/crops ── crops
  ├─ /api/live ── summary + ETag / activity
  └─ /api/admin ── users, settings, simulator, exports, seed
       │
       ▼
MongoDB Atlas / cropmind
  ├─ crops
  ├─ users
  ├─ refresh_tokens
  ├─ recommendations
  ├─ comparisons
  ├─ settings
  ├─ activity_logs
  └─ login_attempts
```

## Production configuration
Frontend: https://crop-mind-rouge.vercel.app  
Backend: https://crop-mind-api.vercel.app  
OpenAPI: https://crop-mind-api.vercel.app/docs

## Environment key contract
Frontend: `VITE_API_BASE_URL`, `VITE_LIVE_POLL_INTERVAL_MS`, `VITE_APP_NAME`.  
Backend: `MONGODB_URI`, `DB_NAME`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS`, `FRONTEND_ORIGIN`, `CRON_SECRET`, `SIMULATOR_ENABLED`, `ADMIN_SEED_EMAIL`, `ADMIN_SEED_PASSWORD`, `SEED_TOKEN`, `ENVIRONMENT`, `LOG_LEVEL`.

## Operator-owned steps
The operator supplies secret values in Vercel and performs the protected Postman seed request. Do not expose credentials or run the seed automatically. After the operator confirms the seed is complete, verify the expected crop and administrator counts and run the limited production smoke checks.
