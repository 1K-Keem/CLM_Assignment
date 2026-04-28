# Architecture

This project is a local centralized logging demo for a movie-ticket booking app.

## Components

- FastAPI app: serves movie browsing, local auth, seat holds, booking confirmation, cancellation, admin demo actions, and JSON APIs.
- SQLite: stores movies, screens, seats, users, sessions, temporary holds, bookings, concessions, and admin demo events in `app/data/cinema.db`.
- JSON Lines logs: the app writes one JSON object per line under the root `logs/` directory.
- Grafana Alloy: tails the log files and pushes entries to Loki.
- Loki: stores logs for querying.
- Grafana: visualizes and explores Loki logs.

## Log Files

- `logs/app.log`: request, browse, and admin logs.
- `logs/auth.log`: login, logout, authorization, verification, and password reset logs.
- `logs/booking.log`: seat, hold, booking, cancellation, and concession logs.
- `logs/error.log`: unexpected app errors.
- `logs/payment.log`: existing payment simulator logs.

## Data Flow

1. A user opens the FastAPI app and browses movies.
2. Request middleware assigns a `request_id` and `session_id`.
3. The app writes structured JSON Lines logs to `logs/*.log`.
4. Alloy tails the mounted files from `/var/log/movie-ticket/*.log` and `/var/log/payment.log`.
5. Alloy forwards logs to Loki at `http://loki:3100`.
6. Grafana queries Loki with labels such as `service`, `log_type`, and `env`.

The booking system is intentionally demo-grade. Holds expire during normal request handling rather than through a background worker.
