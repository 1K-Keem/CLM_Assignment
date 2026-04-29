from datetime import datetime, timezone
import asyncio
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import (
    admin_stats,
    cancel_booking,
    confirm_booking,
    create_hold,
    ensure_session,
    expire_old_holds,
    fetch_booking,
    fetch_booking_seats,
    fetch_hold_showtime_id,
    fetch_movie,
    fetch_movies,
    fetch_seats_for_showtime,
    fetch_showtime,
    fetch_showtimes_for_movie,
    fetch_ticket_prices,
    fetch_upcoming_showtimes,
    get_user_by_session,
    get_user_by_username,
    initialize_database,
    release_hold,
    run_admin_action,
    set_session_user,
    verify_password,
)
from app.logging_config import log_event, request_id_var, session_id_var, user_id_var


app = FastAPI(title="Movie Ticket Web")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
RATE_LIMIT: dict[str, list[float]] = {}


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def render(request: Request, template: str, context: dict) -> HTMLResponse:
    context.setdefault("current_user", getattr(request.state, "user", None))
    return templates.TemplateResponse(template, {"request": request, **context})


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def current_user(request: Request):
    return getattr(request.state, "user", None)


def require_user(request: Request):
    user = current_user(request)
    if user is None:
        log_event("unauthorized_access_blocked", "auth", level="WARN", path=request.url.path, reason="login_required", message="Login required")
        raise HTTPException(status_code=401, detail="Login required")
    return user


def require_admin(request: Request):
    user = require_user(request)
    if user["role"] != "admin":
        log_event("unauthorized_access_blocked", "auth", level="WARN", path=request.url.path, user_id=user["id"], reason="admin_required", message="Admin role required")
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def booking_flow_id(session_id: str, showtime_id: Optional[int] = None, hold_id: str = "") -> str:
    if showtime_id is not None:
        return f"flow_{uuid.uuid5(uuid.NAMESPACE_URL, f'{session_id}:{showtime_id}').hex[:16]}"
    return f"flow_{uuid.uuid5(uuid.NAMESPACE_URL, f'{session_id}:{hold_id}').hex[:16]}"


@app.middleware("http")
async def request_context(request: Request, call_next):
    started = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    session_id = request.cookies.get("cinema_session_id") or f"sess_{uuid.uuid4().hex[:16]}"
    request_id_var.set(request_id)
    session_id_var.set(session_id)
    ensure_session(session_id)
    user = get_user_by_session(session_id)
    request.state.session_id = session_id
    request.state.user = user
    user_id_var.set(str(user["id"]) if user else "")

    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{request.url.path}"
    window = time.time() - 60
    RATE_LIMIT[key] = [stamp for stamp in RATE_LIMIT.get(key, []) if stamp > window]
    RATE_LIMIT[key].append(time.time())
    if request.url.path.startswith("/demo/rate-limit") or len(RATE_LIMIT[key]) > 80:
        log_event("too_many_requests", "request", level="WARN", ip=ip, method=request.method, path=request.url.path, status_code=429, message="Demo rate limit triggered")
        response = JSONResponse({"status": "error", "message": "Too many requests"}, status_code=429)
        response.set_cookie("cinema_session_id", session_id, httponly=True, samesite="lax")
        return response

    try:
        response = await call_next(request)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event("request_failed", "request", level="ERROR", ip=ip, method=request.method, path=request.url.path, status_code=500, latency_ms=latency_ms, reason=exc.__class__.__name__, message="Unhandled request error")
        log_event("unhandled_exception", "error", level="ERROR", ip=ip, method=request.method, path=request.url.path, status_code=500, latency_ms=latency_ms, reason=exc.__class__.__name__, message=str(exc))
        raise

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    status_code = response.status_code
    if request.url.path != "/health":
        if status_code == 404:
            log_event("endpoint_not_found", "request", level="WARN", ip=ip, method=request.method, path=request.url.path, status_code=status_code, latency_ms=latency_ms, message="Endpoint not found")
        elif 400 <= status_code < 500:
            log_event("request_rejected", "request", level="WARN", ip=ip, method=request.method, path=request.url.path, status_code=status_code, latency_ms=latency_ms, message="Request rejected")
        elif status_code >= 500:
            log_event("request_failed", "request", level="ERROR", ip=ip, method=request.method, path=request.url.path, status_code=status_code, latency_ms=latency_ms, message="Request failed")
        else:
            log_event("request_success", "request", ip=ip, method=request.method, path=request.url.path, status_code=status_code, latency_ms=latency_ms, message="Request completed")
        if latency_ms > 500:
            log_event("slow_request", "request", level="WARN", ip=ip, method=request.method, path=request.url.path, status_code=status_code, latency_ms=latency_ms, message="Slow request detected")
    response.set_cookie("cinema_session_id", session_id, httponly=True, samesite="lax")
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    wants_json = request.url.path.startswith("/api") or request.url.path.startswith("/bookings/confirm")
    if wants_json or request.headers.get("accept", "").startswith("application/json"):
        return JSONResponse({"status": "error", "message": exc.detail}, status_code=exc.status_code)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "current_user": getattr(request.state, "user", None),
            "status_code": exc.status_code,
            "message": exc.detail,
        },
        status_code=exc.status_code,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "movie-ticket-web"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    log_event("movie_list_viewed", "browse", path="/", message="Homepage viewed")
    return render(request, "index.html", {"movies": fetch_movies(featured_only=True), "showtimes": fetch_upcoming_showtimes()})


@app.get("/movies", response_class=HTMLResponse)
def movies(request: Request) -> HTMLResponse:
    log_event("movie_list_viewed", "browse", path="/movies", message="Movie catalog viewed")
    return render(request, "movies.html", {"movies": fetch_movies()})


@app.get("/movies/{movie_id}", response_class=HTMLResponse)
def movie_detail(movie_id: int, request: Request) -> HTMLResponse:
    movie = fetch_movie(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    log_event("movie_detail_viewed", "browse", movie_id=movie_id, message="Movie detail viewed")
    return render(request, "movie_detail.html", {"movie": movie, "showtimes": fetch_showtimes_for_movie(movie_id), "prices": fetch_ticket_prices()})


@app.get("/showtimes/{showtime_id}/seats", response_class=HTMLResponse)
def showtime_seats(showtime_id: int, request: Request) -> HTMLResponse:
    showtime = fetch_showtime(showtime_id)
    if showtime is None:
        raise HTTPException(status_code=404, detail="Showtime not found")
    flow_id = booking_flow_id(request.state.session_id, showtime_id)
    for hold in expire_old_holds():
        log_event("seat_hold_expired", "hold", showtime_id=hold["showtime_id"], booking_flow_id=booking_flow_id(request.state.session_id, hold["showtime_id"]), seat_id=hold["seat_id"], reason="expired", message="Seat hold expired")
    seats = fetch_seats_for_showtime(showtime_id, request.state.session_id)
    log_event("seatmap_viewed", "seat", showtime_id=showtime_id, hall_id=showtime["screen_id"], booking_flow_id=flow_id, message="Seat map viewed")
    changed = [seat["seat_code"] for seat in seats if seat["status"] in {"held", "held_by_you", "booked"}]
    if changed:
        log_event("seat_status_changed_while_viewing", "seat", level="WARN", showtime_id=showtime_id, hall_id=showtime["screen_id"], booking_flow_id=flow_id, seat_ids=changed[:8], reason="held_or_booked", message="Seat status changed while viewing")
    addons = [
        {"key": "popcorn", "name": "Popcorn", "price_vnd": 55000},
        {"key": "coke", "name": "Coke", "price_vnd": 30000},
        {"key": "combo", "name": "Combo", "price_vnd": 79000},
        {"key": "water", "name": "Water", "price_vnd": 20000},
        {"key": "nachos", "name": "Nachos", "price_vnd": 65000},
    ]
    return render(request, "seats.html", {"showtime": showtime, "seats": seats, "addons": addons})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return render(request, "login.html", {"error": ""})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    user = get_user_by_username(username)
    if user is None:
        log_event("login_failed_user_not_found", "auth", level="WARN", reason="user_not_found", message="Login failed: user not found")
        return redirect("/login?error=user_not_found")
    if user["locked"]:
        log_event("login_failed_account_locked", "auth", level="WARN", user_id=user["id"], reason="account_locked", message="Login failed: account locked")
        return redirect("/login?error=account_locked")
    if not verify_password(user, password):
        log_event("login_failed_invalid_password", "auth", level="WARN", user_id=user["id"], reason="invalid_password", message="Login failed: invalid password")
        log_event("login_failed", "auth", level="WARN", user_id=user["id"], reason="invalid_password", message="Login failed")
        return redirect("/login?error=invalid_password")
    set_session_user(request.state.session_id, user["id"])
    user_id_var.set(str(user["id"]))
    event = "admin_login_success" if user["role"] == "admin" else "login_success"
    log_event(event, "auth", user_id=user["id"], message="Login successful")
    return redirect("/admin" if user["role"] == "admin" else "/movies")


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    user = current_user(request)
    set_session_user(request.state.session_id, None)
    log_event("logout_success", "auth", user_id=user["id"] if user else None, message="Logout successful")
    return redirect("/")


@app.post("/demo/email-verification")
def demo_email_verification(request: Request) -> JSONResponse:
    user = require_user(request)
    log_event("email_verification_sent", "auth", user_id=user["id"], message="Email verification sent")
    log_event("email_verified", "auth", user_id=user["id"], message="Email verified")
    return JSONResponse({"status": "success", "message": "Email verification demo complete"})


@app.post("/demo/password-reset")
def demo_password_reset(username: str = Form("user@example.com")) -> JSONResponse:
    user = get_user_by_username(username)
    log_event("password_reset_requested", "auth", user_id=user["id"] if user else None, message="Password reset requested")
    if user is None or user["locked"]:
        log_event("password_reset_failed", "auth", level="WARN", user_id=user["id"] if user else None, reason="invalid_or_locked_user", message="Password reset failed")
        return JSONResponse({"status": "error", "message": "Password reset failed"}, status_code=400)
    log_event("password_reset_success", "auth", user_id=user["id"], message="Password reset demo succeeded")
    return JSONResponse({"status": "success", "message": "Password reset demo complete"})


@app.post("/api/showtimes/{showtime_id}/holds")
async def hold_seats(showtime_id: int, request: Request) -> JSONResponse:
    user = require_user(request)
    data = await request.form()
    seat_ids = parse_csv(str(data.get("seat_ids", "")))
    addons = parse_csv(str(data.get("addons", "")))
    expire_seconds = int(data.get("expire_seconds")) if data.get("expire_seconds") else None
    flow_id = booking_flow_id(request.state.session_id, showtime_id)
    log_event("seat_hold_requested", "hold", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, seat_ids=seat_ids, message="Seat hold requested")
    for seat in seat_ids:
        log_event("seat_selected", "seat", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, seat_id=seat, message="Seat selected")
    for addon in addons:
        log_event("concession_added", "concession", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, message=f"Concession added: {addon}")
    status, payload = create_hold(showtime_id, seat_ids, request.state.session_id, user["id"], expire_seconds)
    if status == "success":
        log_event("seat_hold_success", "hold", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, seat_ids=payload["seat_ids"], amount=payload["amount"], currency="VND", message="Seat hold created")
        return JSONResponse({"status": "success", **payload})
    event = {
        "booked": "seat_hold_failed_already_booked",
        "held": "seat_hold_failed_already_held",
        "double_hold": "double_hold_attempt_detected",
    }.get(status, "booking_failed")
    category = "hold" if event.startswith("seat_hold") or event.startswith("double") else "booking"
    log_event(event, category, level="WARN", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, seat_ids=payload.get("seat_ids"), reason=payload.get("reason"), message=payload.get("message"))
    if status == "booked":
        log_event("already_booked_seat_selected", "seat", level="WARN", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, seat_ids=payload.get("seat_ids"), reason="already_booked", message="Booked seat selected")
    if status == "held":
        log_event("held_by_other_seat_selected", "seat", level="WARN", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, seat_ids=payload.get("seat_ids"), reason="already_held", message="Seat held by another session")
    return JSONResponse({"status": "error", **payload}, status_code=409)


@app.delete("/api/holds/{hold_id}")
def release_hold_route(hold_id: str, request: Request) -> JSONResponse:
    user = require_user(request)
    seats = release_hold(hold_id, request.state.session_id)
    for seat in seats:
        log_event("seat_unselected", "seat", user_id=user["id"], seat_id=seat, message="Seat unselected")
    log_event("seat_hold_released", "hold", user_id=user["id"], seat_ids=seats, message="Seat hold released")
    return JSONResponse({"status": "success", "seat_ids": seats})


@app.post("/bookings/confirm")
async def confirm_booking_route(request: Request) -> JSONResponse:
    user = require_user(request)
    data = await request.form()
    hold_id = str(data.get("hold_id", ""))
    addons = parse_csv(str(data.get("addons", "")))
    idempotency_key = str(data.get("idempotency_key") or f"idem_{uuid.uuid4().hex[:12]}")
    showtime_id = fetch_hold_showtime_id(hold_id, request.state.session_id)
    flow_id = booking_flow_id(request.state.session_id, showtime_id, hold_id)
    log_event("booking_requested", "booking", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, message="Booking requested")
    status, payload = confirm_booking(hold_id, request.state.session_id, user["id"], addons, idempotency_key)
    if status == "success":
        flow_id = booking_flow_id(request.state.session_id, payload["showtime_id"])
        log_event("booking_created", "booking", user_id=user["id"], booking_id=payload["booking_id"], showtime_id=payload["showtime_id"], booking_flow_id=flow_id, seat_ids=payload["seat_ids"], amount=payload["amount"], currency="VND", message="Booking record created")
        log_event("booking_confirmed", "booking", user_id=user["id"], booking_id=payload["booking_id"], showtime_id=payload["showtime_id"], booking_flow_id=flow_id, seat_ids=payload["seat_ids"], amount=payload["amount"], currency="VND", message="Booking confirmed")
        log_event("booking_success", "booking", user_id=user["id"], booking_id=payload["booking_id"], showtime_id=payload["showtime_id"], booking_flow_id=flow_id, amount=payload["amount"], currency="VND", message="Booking succeeded")
        log_event("concession_checkout_summary", "concession", user_id=user["id"], booking_id=payload["booking_id"], showtime_id=payload["showtime_id"], booking_flow_id=flow_id, amount=payload["amount"], currency="VND", message="Concession checkout summary")
        return JSONResponse({"status": "success", **payload})
    event = {
        "duplicate": "duplicate_booking_request_detected",
        "expired": "booking_failed_hold_expired",
        "conflict": "booking_failed_seat_conflict",
    }.get(status, "booking_failed")
    log_event(event, "booking", level="WARN", user_id=user["id"], showtime_id=showtime_id, booking_flow_id=flow_id, reason=payload.get("reason"), booking_id=payload.get("booking_id"), message=payload.get("message"))
    return JSONResponse({"status": "error", **payload}, status_code=409)


@app.get("/bookings/{booking_id}", response_class=HTMLResponse)
def booking_detail(booking_id: int, request: Request) -> HTMLResponse:
    user = require_user(request)
    booking = fetch_booking(booking_id)
    if booking is None or (booking["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(status_code=404, detail="Booking not found")
    return render(request, "booking.html", {"booking": booking, "seats": fetch_booking_seats(booking_id)})


@app.post("/bookings/{booking_id}/cancel")
def cancel_booking_route(booking_id: int, request: Request) -> RedirectResponse:
    user = require_user(request)
    status, payload = cancel_booking(booking_id, user["id"], admin=user["role"] == "admin")
    if status == "success":
        log_event("booking_canceled_by_user", "cancel", user_id=user["id"], booking_id=booking_id, seat_ids=payload["seat_ids"], amount=payload["amount"], currency="VND", message="Booking canceled by user")
        log_event("seat_released_after_cancel", "cancel", user_id=user["id"], booking_id=booking_id, seat_ids=payload["seat_ids"], message="Seats released after cancel")
    return redirect(f"/bookings/{booking_id}")


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request) -> HTMLResponse:
    user = require_admin(request)
    return render(request, "admin.html", {"stats": admin_stats(), "admin_user": user})


@app.post("/admin/actions/{event}")
def admin_action(event: str, request: Request) -> RedirectResponse:
    user = require_admin(request)
    message = run_admin_action(event, user["id"])
    log_event(event, "admin", user_id=user["id"], message=message)
    return redirect("/admin")


@app.get("/demo/timeout")
async def demo_timeout() -> JSONResponse:
    await asyncio.sleep(0.6)
    log_event("request_timeout", "request", level="WARN", status_code=504, latency_ms=600, reason="demo_timeout", message="Demo timeout simulated")
    log_event("booking_timeout", "booking", level="WARN", reason="demo_timeout", message="Demo booking timeout simulated")
    return JSONResponse({"status": "error", "message": "Demo timeout"}, status_code=504)


@app.post("/demo/expired-hold/{showtime_id}")
def demo_expired_hold(showtime_id: int, request: Request) -> JSONResponse:
    user = require_user(request)
    status, payload = create_hold(showtime_id, ["A1"], request.state.session_id, user["id"], expire_seconds=-1)
    for hold in expire_old_holds():
        log_event("seat_hold_expired", "hold", user_id=user["id"], showtime_id=hold["showtime_id"], seat_id=hold["seat_id"], reason="expired", message="Demo hold expired")
    if status == "success":
        return JSONResponse({"status": "success", **payload})
    return JSONResponse({"status": "error", **payload}, status_code=409)
