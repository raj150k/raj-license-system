# RA J License Website (Starter)

## Before publishing
1. Regenerate the database API key because the previous key was exposed in chat/screenshot.
2. Keep the new key private. Do not paste it into `app.py`, GitHub, or screenshots.
3. This starter expects the provider's HTTP SQL API to return SELECT rows as JSON under `rows`, `data`, `results`, or `result`. If its response format differs, the dashboard/verification parser may need a small adjustment.

## Files
- `app.py`: Flask website, admin login, license generation, public verification API
- `requirements.txt`: Python packages
- `render.yaml`: Render service setup

## Render environment variables
- `DB_API_KEY`: newly regenerated API key
- `ADMIN_USERNAME`: choose your admin username
- `ADMIN_PASSWORD`: create a strong, unique password
- `SECRET_KEY`: a long random secret (Render can generate it)
- `DB_API_URL` and `DB_NAME` are already set in render.yaml

## API test
POST `/api/verify` with JSON:
```json
{"license_key":"RAJ-XXXX-XXXX-XXXX-XXXX","device_id":"DEVICE-001"}
```

## Important limitations
This is a starter project, not a production-grade licensing platform. The first device is bound to the license; changing devices consumes another activation. The current simple read-then-update flow can race under simultaneous requests. Add atomic database transactions/rate limiting and test the provider API response before using it for real customers.
