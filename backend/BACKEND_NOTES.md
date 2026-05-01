# Backend — What Was Built & What's Next

## Project Overview

Python/Flask REST API that acts as a proxy and cache layer between the browser and the MTA API. The frontend never calls the MTA API directly — all data flows through this backend.

---

## Folder Structure

```
backend/
  app/
    __init__.py          # App factory — wires up DB, CORS, Firebase, scheduler, blueprints
    config.py            # Loads env vars via python-dotenv
    extensions.py        # SQLAlchemy singleton (db)
    models.py            # ORM models for all 5 DB tables
    mta_client.py        # MTA GTFS-RT fetcher functions
    scheduler.py         # APScheduler background polling jobs
    firebase.py          # Firebase Admin SDK init + @verify_token decorator
    routes/
      __init__.py
      status.py          # GET /api/status, GET /api/status/<route_id>
      vehicles.py        # GET /api/vehicles
      stations.py        # GET /api/stations/<station_id>
      accessibility.py   # GET /api/accessibility/<station_id>, GET /api/accessibility
      favorites.py       # Full CRUD + alert toggle (all auth-protected)
  tests/
    conftest.py          # In-memory SQLite fixtures, app/client/db fixtures
    test_mta_client.py   # Unit tests for _classify_alert, _map_equipment_status
    test_status.py       # Tests for /api/status endpoints
    test_favorites.py    # Integration tests for all /api/favorites endpoints
  run.py                 # Entry point — python run.py
  requirements.txt       # All Python dependencies pinned
  .env.example           # Template for required environment variables
  README.md              # Quick-start guide
```

---

## What Was Built

### 1. App Factory (`app/__init__.py`)
- Creates the Flask app, applies CORS, initializes SQLAlchemy, Firebase, and APScheduler
- Registers all route blueprints
- Calls `db.create_all()` on startup so tables are created automatically

### 2. Database Models (`app/models.py`)
Five SQLAlchemy ORM models mapping to SQLite tables:

| Model | Table | Purpose |
|---|---|---|
| `ServiceStatus` | `service_status` | Cached MTA route status + alert text |
| `VehiclePosition` | `vehicle_positions` | Live vehicle lat/lon per route |
| `AccessibilityStatus` | `accessibility_status` | Elevator/escalator status per station |
| `User` | `users` | Firebase UID + email, created on first auth |
| `Favorite` | `favorites` | User-saved routes/stations with alert toggle |

Every cached table has a `fetched_at` column so the API can flag stale data (> 5 minutes old).

### 3. MTA API Client (`app/mta_client.py`)
Three fetch functions that call the MTA GTFS-RT feeds:

- `fetch_service_alerts()` — parses the all-alerts protobuf feed, classifies each alert as Good Service / Delays / Service Change / Suspended
- `fetch_vehicle_positions()` — loops over 8 subway line group feeds, extracts lat/lon per vehicle
- `fetch_accessibility_status()` — calls the elevator/escalator equipment JSON endpoint, maps status strings

All functions return plain Python dicts and handle errors gracefully (log + return empty list).

### 4. Background Scheduler (`app/scheduler.py`)
APScheduler runs inside the Flask process with three jobs:

| Job | Interval | What it does |
|---|---|---|
| `poll_service_status` | 30 seconds | Fetches alerts, upserts `service_status` |
| `poll_vehicle_positions` | 30 seconds | Fetches positions, replaces all `vehicle_positions` rows |
| `poll_accessibility` | 60 seconds | Fetches equipment status, upserts `accessibility_status` |

Each job runs inside `app.app_context()` so it has full DB access.

### 5. Firebase Auth (`app/firebase.py`)
- `init_firebase()` — loads the service account JSON and initializes Firebase Admin SDK. Skips gracefully with a warning if the credentials file is missing (so the app still starts without Firebase during development).
- `@verify_token` decorator — extracts the `Authorization: Bearer <token>` header, calls `firebase_admin.auth.verify_id_token()`, and attaches `g.firebase_uid` + `g.email` to the request context. Returns 401 on invalid token, 503 if Firebase isn't configured.

### 6. REST API Endpoints

#### Public (no auth)

| Method | Path | Description |
|---|---|---|
| GET | `/api/status` | All cached service statuses + `stale` flag |
| GET | `/api/status/<route_id>` | Single route status |
| GET | `/api/vehicles` | All vehicle positions + `stale` flag |
| GET | `/api/stations/<station_id>` | Station detail (status + accessibility) |
| GET | `/api/accessibility/<station_id>` | Equipment status for a station |
| GET | `/api/accessibility?operational_only=true` | Only fully accessible stations |

#### Protected (Firebase ID token required)

| Method | Path | Description |
|---|---|---|
| GET | `/api/favorites` | Get authenticated user's favorites |
| POST | `/api/favorites` | Add a favorite (route or station) |
| DELETE | `/api/favorites/<id>` | Remove a favorite |
| PATCH | `/api/favorites/<id>/alerts` | Toggle alert notifications on/off |

### 7. Tests (`tests/`)

| File | What it covers |
|---|---|
| `conftest.py` | In-memory SQLite app fixture, auto-rollback after each test |
| `test_mta_client.py` | Unit tests for alert classification and equipment status mapping |
| `test_status.py` | Empty response, seeded data, single route found/not found |
| `test_favorites.py` | Unauthenticated 401, add/get/delete/toggle with mocked Firebase |

Run with:
```bash
pytest --cov=app tests/
```

---

## What's Next (Planned)

### Frontend Compatibility (MTA folder)
The frontend team built their app in `MTA/` using React + TypeScript + Vite. The backend is fully compatible:
- Calls `GET /api/status` and `GET /api/vehicles` at `http://localhost:5000` (matches our Flask port)
- `api.ts` uses `extractArray()` which handles our `{ "data": [...], "stale": bool }` shape
- `toVehicle()` maps `latitude`/`longitude` — we also now send `lat`/`lon` as primary keys to be explicit
- `toRouteStatus()` maps `severity` directly — we now include `severity` (`good`/`minor`/`major`) and `summary` in every status response
- Frontend has a mock mode (`VITE_USE_MOCK_DATA=true`) for UI dev without the backend running

### Short Term
- [ ] **GTFS Static import** — download and parse the MTA static GTFS zip to populate a `stations` table with real station names, coordinates, and serving routes. Right now `GET /api/stations/<id>` returns what's in cache but has no station name lookup.
- [ ] **Next arrivals** — use the GTFS-RT trip updates feed to calculate next arrival times per station and include them in `GET /api/stations/<station_id>`.
- [ ] **Alert notification dispatch** — when `poll_service_status` finds a new alert for a route, query `favorites` for users with `alerts_enabled=1` on that route and send them an email via Firebase or SendGrid.
- [ ] **Rate limit handling** — add exponential backoff in `mta_client.py` for 429 responses from the MTA API.
- [ ] **Bus routes** — the current vehicle feed only covers subway. Add MTA Bus Time GTFS-RT feeds for bus vehicle positions.
- [ ] **Route geometry** — serve GeoJSON route shapes from the GTFS static `shapes.txt` so the frontend map can draw actual route lines instead of just dots.
- [ ] **Pagination** — `/api/vehicles` can return thousands of rows. Add `?page` and `?limit` query params.
- [ ] **More tests** — add tests for `/api/vehicles`, `/api/accessibility`, and `/api/stations`. Aim for ≥ 80% coverage across all modules.

### If Time Permits (ML Features)
- [ ] **Delay prediction** — train a Random Forest on historical MTA alert data + time-of-day + weather. Serve predictions via `GET /api/predict/delay/<route_id>`.
- [ ] **Crowd estimation** — use MTA's public ridership data (data.ny.gov) with a Prophet time-series model. Serve via `GET /api/predict/crowd/<station_id>`.
- [ ] **Anomaly detection** — Isolation Forest on alert frequency per route to surface unusual disruption patterns.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `MTA_API_KEY` | Yes | From https://api.mta.info (free registration) |
| `FIREBASE_CREDENTIALS_PATH` | Yes (for auth) | Path to Firebase service account JSON |
| `SECRET_KEY` | Yes | Any random string for Flask session signing |
| `DATABASE_URL` | No | Defaults to `sqlite:///mta_transit.db` |
| `FLASK_ENV` | No | Set to `development` for debug mode |

---

## How to Run Locally

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.enc .env            # fill in MTA_API_KEY
python run.py                   # starts on http://localhost:5000
```

## How to Run Tests

```bash
pytest --cov=app tests/
```
