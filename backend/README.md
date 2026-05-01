# NYC MTA Transit App (Backend)

Python/Flask REST API with SQLite cache and Firebase auth.

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.enc .env            # fill in MTA_API_KEY and FIREBASE_CREDENTIALS_PATH
```

## Run

```bash
python run.py
```

API available at `http://localhost:5000`.

## Environment Variables

| Variable | Description |
|---|---|
| `MTA_API_KEY` | Your MTA API key from https://api.mta.info |
| `FIREBASE_CREDENTIALS_PATH` | Path to Firebase service account JSON |
| `SECRET_KEY` | Flask secret key (any random string) |
| `DATABASE_URL` | SQLite path (default: `sqlite:///mta_transit.db`) |

## Run Tests

```bash
pytest --cov=app tests/
```

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | /api/status | No | All service statuses |
| GET | /api/status/:route_id | No | Single route status |
| GET | /api/vehicles | No | All vehicle positions |
| GET | /api/stations/:station_id | No | Station detail |
| GET | /api/accessibility/:station_id | No | Elevator/escalator status |
| GET | /api/accessibility?operational_only=true | No | Fully accessible stations |
| GET | /api/favorites | Yes | User's favorites |
| POST | /api/favorites | Yes | Add favorite |
| DELETE | /api/favorites/:id | Yes | Remove favorite |
| PATCH | /api/favorites/:id/alerts | Yes | Toggle alerts |
