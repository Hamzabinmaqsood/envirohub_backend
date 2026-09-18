# EnviroHub Backend — Citizen MVP

Django REST API foundation for the environmental reporting super-app.

## Included in this starter

- Email-based custom Django user model
- JWT registration/login/refresh/logout
- Citizen profile endpoint
- PostgreSQL + PostGIS spatial storage
- Environmental issue categories
- Citizen reports with GPS point, address, description and 1–5 before photos
- Complaint status timeline
- Per-user notifications and read state
- Swagger/OpenAPI docs
- Docker Compose development environment

## Stack

- Python 3.13
- Django 5.2.17 LTS
- Django REST Framework 3.18.1
- PostgreSQL + PostGIS
- Simple JWT
- drf-spectacular

## Quick start with Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py makemigrations accounts reports notifications
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_categories
docker compose exec web python manage.py createsuperuser
```

Open:

- API docs: http://localhost:8000/api/docs/
- Admin: http://localhost:8000/admin/

## Citizen API

### Authentication

- `POST /api/v1/auth/register/`
- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/refresh/`
- `POST /api/v1/auth/logout/` — body: `{"refresh": "..."}`
- `GET/PATCH /api/v1/auth/me/`

### Categories

- `GET /api/v1/categories/`

### Reports

- `POST /api/v1/reports/`
- `GET /api/v1/reports/`
- `GET /api/v1/reports/{uuid}/`
- `GET /api/v1/reports/{uuid}/timeline/`

Create report as `multipart/form-data`:

```text
category=garbage
description=Overflowing garbage beside the road
latitude=33.6844
longitude=73.0479
address=Optional human-readable address
images=<file1>
images=<file2>
```

Notes:

- Coordinates are stored as a PostGIS `PointField` (`longitude`, then `latitude`).
- A citizen only sees their own reports.
- 1–5 JPEG/PNG/WebP images are accepted, max 10 MB each.

### Notifications

- `GET /api/v1/notifications/`
- `PATCH /api/v1/notifications/{uuid}/read/`
- `PATCH /api/v1/notifications/read-all/`

## Status flow

```text
SUBMITTED -> VERIFIED -> ASSIGNED -> IN_PROGRESS -> RESOLVED
                 |                         |
                 -> REJECTED              -> REOPENED
```

Citizen-side endpoints do not allow status changes. Status transitions will be owned by the future authority/worker modules.

## Next implementation slice

1. Add worker/authority roles and permissions.
2. Add admin status-transition service that always writes history + notification atomically.
3. Add Firebase device tokens / push notifications.
4. Add reverse geocoding strategy.
5. Add nearby/duplicate-report detection using PostGIS distance queries.
6. Connect the Flutter Citizen App.
