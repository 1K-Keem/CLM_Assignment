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

## Grafana, Loki, Alloy

```bash
cd infra
docker compose up -d
```

Open Grafana at `http://localhost:3000`, add Loki with URL `http://loki:3100`, then query in Explore.

Useful LogQL:

```logql
{service="movie-ticket-web"}
{service="movie-ticket-web",log_type="auth"} |= "login_failed"
{service="movie-ticket-web",log_type="booking"} |= "booking_failed"
{service="movie-ticket-web"} |= "slow_request"
{service="movie-ticket-web",log_type="booking"} |= "seat_conflict"
{service="movie-ticket-web",log_type="booking"} |= "seat_hold_expired"
sum by (log_type) (count_over_time({service="movie-ticket-web"}[5m]))
{service="movie-ticket-web",log_type="error"}
```
