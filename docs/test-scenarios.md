# Test Scenarios

## Run Locally

```bash
rtk python3 -m pip install -r app/requirements.txt
rtk python3 -m app.seed
rtk python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Demo users:

- Customer: `user@example.com` / `demo123`
- Admin: `admin@example.com` / `admin123`
- Locked: `locked@example.com` / `locked123`

## Generate Logs

Use browser flows or curl with a cookie jar:

```bash
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i http://127.0.0.1:8000/movies
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST -d 'username=user@example.com&password=demo123' http://127.0.0.1:8000/login
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST -d 'seat_ids=A1,A2&addons=popcorn,coke' http://127.0.0.1:8000/api/showtimes/101/holds
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST -d 'hold_id=RETURNED_HOLD_ID&addons=popcorn,coke&idempotency_key=demo-1' http://127.0.0.1:8000/bookings/confirm
```

Auth failures:

```bash
rtk curl -i -X POST -d 'username=missing@example.com&password=nope' http://127.0.0.1:8000/login
rtk curl -i -X POST -d 'username=user@example.com&password=nope' http://127.0.0.1:8000/login
rtk curl -i -X POST -d 'username=locked@example.com&password=locked123' http://127.0.0.1:8000/login
```

Failure demos:

```bash
rtk curl -i http://127.0.0.1:8000/admin
rtk curl -i http://127.0.0.1:8000/not-found-demo
rtk curl -i http://127.0.0.1:8000/demo/timeout
rtk curl -i http://127.0.0.1:8000/demo/rate-limit
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST http://127.0.0.1:8000/demo/expired-hold/101
```

Admin logs:

```bash
rtk curl -c /tmp/admin.cookies -b /tmp/admin.cookies -i -X POST -d 'username=admin@example.com&password=admin123' http://127.0.0.1:8000/login
rtk curl -c /tmp/admin.cookies -b /tmp/admin.cookies -i -X POST http://127.0.0.1:8000/admin/actions/pricing_updated
```

## CLM Incident Playbooks

### Auth failure

1. Trigger invalid logins:

```bash
rtk curl -i -X POST -d 'username=missing@example.com&password=nope' http://127.0.0.1:8000/login
rtk curl -i -X POST -d 'username=user@example.com&password=nope' http://127.0.0.1:8000/login
rtk curl -i -X POST -d 'username=locked@example.com&password=locked123' http://127.0.0.1:8000/login
```

2. Query failures:

```logql
{service="movie-ticket-web",log_type="auth",env="development"} | json | event =~ "login_failed.*"
```

3. Check `reason`, `user_id`, `session_id`, `request_id`, and nearby `request_rejected` entries.

### Seat conflict

1. Login in two cookie jars, hold the same seat from the first session, then hold it from the second session:

```bash
rtk curl -c /tmp/cinema-a.cookies -b /tmp/cinema-a.cookies -i -X POST -d 'username=user@example.com&password=demo123' http://127.0.0.1:8000/login
rtk curl -c /tmp/cinema-a.cookies -b /tmp/cinema-a.cookies -i -X POST -d 'seat_ids=A1' http://127.0.0.1:8000/api/showtimes/101/holds
rtk curl -c /tmp/cinema-b.cookies -b /tmp/cinema-b.cookies -i -X POST -d 'username=admin@example.com&password=admin123' http://127.0.0.1:8000/login
rtk curl -c /tmp/cinema-b.cookies -b /tmp/cinema-b.cookies -i -X POST -d 'seat_ids=A1' http://127.0.0.1:8000/api/showtimes/101/holds
```

2. Query conflict logs:

```logql
{service="movie-ticket-web",log_type="booking",env="development"} | json | event =~ "seat_hold_failed_already_held|held_by_other_seat_selected|booking_failed_seat_conflict"
```

3. Pivot on `booking_flow_id` to see the seatmap, hold request, and failure chain.

### Hold expired

1. Login, create an expired demo hold, then inspect hold expiry:

```bash
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST -d 'username=user@example.com&password=demo123' http://127.0.0.1:8000/login
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST http://127.0.0.1:8000/demo/expired-hold/101
```

2. Query:

```logql
{service="movie-ticket-web",log_type="booking",env="development"} | json | event =~ "seat_hold_expired|booking_failed_hold_expired"
```

### Duplicate booking

1. Confirm a valid hold twice with the same idempotency key:

```bash
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST -d 'seat_ids=A2&addons=combo' http://127.0.0.1:8000/api/showtimes/101/holds
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST -d 'hold_id=RETURNED_HOLD_ID&addons=combo&idempotency_key=duplicate-demo-1' http://127.0.0.1:8000/bookings/confirm
rtk curl -c /tmp/cinema.cookies -b /tmp/cinema.cookies -i -X POST -d 'hold_id=RETURNED_HOLD_ID&addons=combo&idempotency_key=duplicate-demo-1' http://127.0.0.1:8000/bookings/confirm
```

2. Query:

```logql
{service="movie-ticket-web",log_type="booking",env="development"} | json | event="duplicate_booking_request_detected"
```

### Slow request

1. Trigger timeout demo:

```bash
rtk curl -i http://127.0.0.1:8000/demo/timeout
```

2. Query slow and failed request logs:

```logql
{service="movie-ticket-web",log_type="app",env="development"} | json | event =~ "slow_request|request_timeout|request_failed"
```

### Admin audit

1. Login as admin and run a demo admin action:

```bash
rtk curl -c /tmp/admin.cookies -b /tmp/admin.cookies -i -X POST -d 'username=admin@example.com&password=admin123' http://127.0.0.1:8000/login
rtk curl -c /tmp/admin.cookies -b /tmp/admin.cookies -i -X POST http://127.0.0.1:8000/admin/actions/pricing_updated
```

2. Query:

```logql
{service="movie-ticket-web",log_type="app",env="development"} | json | category="admin"
```

## Grafana, Loki, Alloy

```bash
cd infra
docker compose up -d
```

Open Grafana at `http://localhost:3000`, add Loki with URL `http://loki:3100`, then query in Explore.

Useful LogQL:

```logql
{service="movie-ticket-web",env="development"} | json
{service="movie-ticket-web",log_type="auth",env="development"} | json | event =~ "login_failed.*|unauthorized_access_blocked"
{service="movie-ticket-web",log_type="booking",env="development"} | json | event =~ "booking_failed.*|seat_hold_failed.*|duplicate_booking_request_detected"
{service="movie-ticket-web",log_type="app",env="development"} | json | event="slow_request"
{service="movie-ticket-web",log_type="booking",env="development"} | json | booking_flow_id != ""
sum by (log_type) (count_over_time({service="movie-ticket-web",env="development"} | json [5m]))
{service="movie-ticket-web",log_type="error",env="development"} | json
```
