# Log Catalog

All movie app logs use JSON Lines with stable fields:

```json
{"timestamp":"2026-04-28T03:00:00+00:00","level":"INFO","service":"movie-ticket-web","environment":"development","event":"booking_confirmed","category":"booking","request_id":"req_abc","session_id":"sess_abc","user_id":"1","booking_id":1,"seat_ids":["A1"],"amount":220000,"currency":"VND","message":"Booking confirmed"}
```

## Request And Browse

| Event | Category | Meaning | Important fields |
| --- | --- | --- | --- |
| `request_success` | request | HTTP request completed below error threshold | method, path, status_code, latency_ms, ip |
| `request_failed` | request | Request returned or raised an error | method, path, status_code, reason |
| `slow_request` | request | Request latency exceeded demo threshold | path, latency_ms |
| `endpoint_not_found` | request | 404 route | path, status_code |
| `request_timeout` | request | Demo timeout route triggered | status_code, latency_ms, reason |
| `too_many_requests` | request | Demo rate limit triggered | ip, path, status_code |
| `movie_list_viewed` | browse | Homepage or catalog viewed | path |
| `movie_detail_viewed` | browse | Movie detail page viewed | movie_id |

## Auth

| Event | Meaning |
| --- | --- |
| `login_success` | Customer login succeeded |
| `admin_login_success` | Admin login succeeded |
| `login_failed` | Generic failed login |
| `login_failed_invalid_password` | Known user with bad password |
| `login_failed_user_not_found` | Unknown username |
| `login_failed_account_locked` | Locked account attempted login |
| `logout_success` | User logged out |
| `unauthorized_access_blocked` | Protected route blocked |
| `email_verification_sent`, `email_verified` | Demo verification events |
| `password_reset_requested`, `password_reset_success`, `password_reset_failed` | Demo reset events |

## Booking

| Event | Category | Meaning |
| --- | --- | --- |
| `seatmap_viewed` | seat | User viewed seats for a showtime |
| `seat_selected`, `seat_unselected` | seat | UI selection or release action |
| `already_booked_seat_selected` | seat | User tried a booked seat |
| `held_by_other_seat_selected` | seat | User tried a seat held by another session |
| `seat_hold_requested` | hold | Hold API called |
| `seat_hold_success` | hold | Seats held temporarily |
| `seat_hold_failed_already_booked` | hold | Hold rejected by booked seat |
| `seat_hold_failed_already_held` | hold | Hold rejected by active hold |
| `seat_hold_expired` | hold | Old hold expired |
| `seat_hold_released` | hold | Hold manually released |
| `double_hold_attempt_detected` | hold | Same session tried to hold held seats twice |
| `booking_requested` | booking | Confirm API called |
| `booking_created` | booking | DB booking row created |
| `booking_confirmed`, `booking_success` | booking | Booking completed |
| `booking_failed`, `booking_failed_seat_conflict`, `booking_failed_hold_expired` | booking | Booking failed |
| `duplicate_booking_request_detected` | booking | Idempotency key reused |
| `booking_timeout` | booking | Demo timeout triggered |
| `booking_canceled_by_user`, `seat_released_after_cancel` | cancel | Booking cancellation released seats |
| `concession_added`, `concession_checkout_summary` | concession | Snack selection and checkout |

## Admin

Admin events are logged in `logs/app.log`: `movie_created`, `movie_updated`, `movie_deleted`, `showtime_created`, `showtime_updated`, `showtime_deleted`, `pricing_updated`, `seatmap_updated`, `manual_booking_created`, and `manual_booking_canceled`.
