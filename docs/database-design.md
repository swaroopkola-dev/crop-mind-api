# CropMind database design

Database: `cropmind` on MongoDB Atlas. Application data is grouped into eight collections.

| Collection | Purpose | Main fields |
|---|---|---|
| crops | Active suitability profiles | name, name_key, ranges, soil_types, seasons, dataset_version, source, is_synthetic |
| users | Accounts and roles | email, password_hash, role, status, display_name |
| refresh_tokens | Rotating sessions | user_id, token_hash, expires_at, revoked_at |
| recommendations | Ranked field assessments | owner_id, inputs, ranked_results, explanation_source, created_at, is_synthetic |
| comparisons | Side-by-side crop scoring | owner_id, crop_ids, inputs, results, created_at |
| settings | Supported application configuration | key, value, updated_at, updated_by |
| activity_logs | Audit and operational activity | action, actor_id, actor_role, entity_type, timestamp, source, is_synthetic |
| login_attempts | Authentication abuse controls | normalized identity, attempt metadata, timestamps |

## Indexes and ownership
Startup calls the shared index initializer. Unique indexes protect normalized user email, crop name key and refresh token hash. Query indexes support history by owner/date, synthetic filtering and activity feeds. ObjectIds are serialized to stable string IDs at API boundaries.

## Retention and deletion
Refresh tokens are rotated and revoked. Deleting a user revokes their sessions and removes their ownership association from retained recommendations so aggregate records remain without a direct account link. Synthetic purge targets records explicitly marked `is_synthetic: true`; real records are excluded.

## Seed behavior
The protected seed route uses idempotent upserts for the 15 crop profiles and inserts default settings only when missing. It creates the configured admin account if absent and refuses to silently promote an existing non-admin account. Seed is an operator-controlled action and was not run during this build.
