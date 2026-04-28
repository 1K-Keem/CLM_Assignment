from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "cinema.db"
HOLD_MINUTES = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return digest.hex()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                genre TEXT NOT NULL,
                rating TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                synopsis TEXT NOT NULL,
                cast TEXT NOT NULL,
                visual_theme TEXT NOT NULL,
                featured INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS screens (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                seat_rows INTEGER NOT NULL,
                seats_per_row INTEGER NOT NULL,
                format_label TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ticket_prices (
                format TEXT PRIMARY KEY,
                price_vnd INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS showtimes (
                id INTEGER PRIMARY KEY,
                movie_id INTEGER NOT NULL,
                screen_id INTEGER NOT NULL,
                starts_at TEXT NOT NULL,
                format TEXT NOT NULL,
                language TEXT NOT NULL,
                FOREIGN KEY (movie_id) REFERENCES movies(id),
                FOREIGN KEY (screen_id) REFERENCES screens(id)
            );

            CREATE TABLE IF NOT EXISTS seats (
                id INTEGER PRIMARY KEY,
                screen_id INTEGER NOT NULL,
                row_label TEXT NOT NULL,
                seat_number INTEGER NOT NULL,
                seat_code TEXT NOT NULL,
                seat_type TEXT NOT NULL DEFAULT 'standard',
                UNIQUE (screen_id, seat_code),
                FOREIGN KEY (screen_id) REFERENCES screens(id)
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL,
                locked INTEGER NOT NULL DEFAULT 0,
                email_verified INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS seat_holds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                showtime_id INTEGER NOT NULL,
                seat_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                user_id INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (showtime_id) REFERENCES showtimes(id),
                FOREIGN KEY (seat_id) REFERENCES seats(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                showtime_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                idempotency_key TEXT,
                created_at TEXT NOT NULL,
                canceled_at TEXT,
                UNIQUE (user_id, idempotency_key),
                FOREIGN KEY (showtime_id) REFERENCES showtimes(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS booking_seats (
                booking_id INTEGER NOT NULL,
                seat_id INTEGER NOT NULL,
                showtime_id INTEGER NOT NULL,
                PRIMARY KEY (booking_id, seat_id),
                UNIQUE (showtime_id, seat_id),
                FOREIGN KEY (booking_id) REFERENCES bookings(id),
                FOREIGN KEY (seat_id) REFERENCES seats(id)
            );

            CREATE TABLE IF NOT EXISTS booking_addons (
                booking_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price_vnd INTEGER NOT NULL,
                FOREIGN KEY (booking_id) REFERENCES bookings(id)
            );

            CREATE TABLE IF NOT EXISTS admin_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                user_id INTEGER,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        seed_database(connection)


def seed_database(connection: sqlite3.Connection) -> None:
    movies = [
        (1, "Phí Phông: Quỷ Máu Rừng Thiên", "phi-phong-quy-mau-rung-thien", "Kinh dị, tâm linh", "T18", 105, "Một phim Việt đang tạo hiệu ứng phòng vé mạnh, xoay quanh lời nguyền rừng sâu và những bí mật bị chôn giấu.", "Dàn diễn viên Việt Nam", "signal", 1),
        (2, "Thẩm Mỹ Viện Âm Phủ", "tham-my-vien-am-phu", "Hồi hộp, kinh dị", "T18", 99, "Một cơ sở làm đẹp bí ẩn trở thành nơi kéo khán giả vào chuỗi sự kiện rùng rợn, hợp để demo suất chiếu đêm.", "Dàn diễn viên Việt Nam", "neon", 1),
        (3, "Mắt Biếc", "mat-biec", "Tình cảm, chính kịch", "T13", 117, "Chuyện tình day dứt của Ngạn và Hà Lan, một trong những phim Việt được nhớ đến nhiều nhất những năm gần đây.", "Trần Nghĩa, Trúc Anh, Khánh Vân", "lantern", 1),
        (4, "Bố Già", "bo-gia", "Gia đình, hài, chính kịch", "T13", 128, "Câu chuyện cha con đậm chất Sài Gòn, từng là hiện tượng phòng vé Việt với sức lan tỏa đại chúng.", "Trấn Thành, Tuấn Trần, Ngân Chi, Lê Giang", "apricot", 1),
        (5, "Mai", "mai", "Tâm lý, tình cảm", "T18", 131, "Bộ phim của Trấn Thành về một người phụ nữ đi qua tổn thương, cô đơn và lựa chọn yêu thương chính mình.", "Phương Anh Đào, Tuấn Trần, Trấn Thành, Hồng Đào", "orbit", 1),
        (6, "Nhà Bà Nữ", "nha-ba-nu", "Gia đình, hài, chính kịch", "T13", 102, "Một lát cắt gia đình đô thị nhiều xung đột, phù hợp cho nhóm khán giả đi xem cuối tuần.", "Lê Giang, Uyển Ân, Trấn Thành, Song Luân", "lantern", 0),
    ]
    screens = [
        (1, "Cinestar Sinh Viên", 7, 10, "Khu đô thị Đại học Quốc Gia TP.HCM"),
        (2, "Cinestar Quốc Thanh", 6, 8, "Nguyễn Trãi, Quận 1, TP.HCM"),
        (3, "CGV Vincom Đồng Khởi", 7, 9, "Vincom Center Đồng Khởi, Quận 1, TP.HCM"),
        (4, "Galaxy Nguyễn Du", 6, 9, "Nguyễn Du, Quận 1, TP.HCM"),
    ]
    prices = [("2D", 95000), ("3D", 125000), ("IMAX", 175000), ("VIP", 230000)]
    showtimes = [
        (101, 1, 1, "2026-05-01T18:30:00", "2D", "Tiếng Việt"),
        (102, 1, 2, "2026-05-01T21:15:00", "VIP", "Tiếng Việt"),
        (103, 1, 3, "2026-05-02T19:00:00", "IMAX", "Tiếng Việt"),
        (201, 2, 2, "2026-05-01T22:20:00", "2D", "Tiếng Việt"),
        (202, 2, 4, "2026-05-02T20:45:00", "VIP", "Tiếng Việt"),
        (301, 3, 1, "2026-05-01T19:10:00", "2D", "Tiếng Việt"),
        (302, 3, 3, "2026-05-02T16:30:00", "VIP", "Tiếng Việt"),
        (401, 4, 2, "2026-05-01T20:00:00", "2D", "Tiếng Việt"),
        (402, 4, 4, "2026-05-02T18:20:00", "VIP", "Tiếng Việt"),
        (501, 5, 3, "2026-05-01T20:30:00", "IMAX", "Tiếng Việt"),
        (502, 5, 1, "2026-05-02T21:00:00", "VIP", "Tiếng Việt"),
        (601, 6, 4, "2026-05-01T17:40:00", "2D", "Tiếng Việt"),
        (602, 6, 1, "2026-05-02T14:15:00", "2D", "Tiếng Việt"),
    ]
    users = [
        (1, "user@example.com", "Demo User", "demo123", "customer", 0, 1),
        (2, "admin@example.com", "Admin User", "admin123", "admin", 0, 1),
        (3, "locked@example.com", "Locked User", "locked123", "customer", 1, 0),
    ]

    connection.executemany("INSERT OR IGNORE INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", movies)
    connection.executemany(
        """
        UPDATE movies
        SET title = ?, slug = ?, genre = ?, rating = ?, duration_minutes = ?, synopsis = ?,
            cast = ?, visual_theme = ?, featured = ?
        WHERE id = ?
        """,
        [(title, slug, genre, rating, duration, synopsis, cast, theme, featured, movie_id) for movie_id, title, slug, genre, rating, duration, synopsis, cast, theme, featured in movies],
    )
    connection.executemany("INSERT OR IGNORE INTO screens VALUES (?, ?, ?, ?, ?)", screens)
    connection.executemany(
        "UPDATE screens SET name = ?, seat_rows = ?, seats_per_row = ?, format_label = ? WHERE id = ?",
        [(name, rows, seats, label, screen_id) for screen_id, name, rows, seats, label in screens],
    )
    connection.executemany("INSERT OR IGNORE INTO ticket_prices VALUES (?, ?)", prices)
    connection.executemany("UPDATE ticket_prices SET price_vnd = ? WHERE format = ?", [(price, fmt) for fmt, price in prices])
    connection.executemany("INSERT OR IGNORE INTO showtimes VALUES (?, ?, ?, ?, ?, ?)", showtimes)
    connection.executemany(
        "UPDATE showtimes SET movie_id = ?, screen_id = ?, starts_at = ?, format = ?, language = ? WHERE id = ?",
        [(movie_id, screen_id, starts_at, fmt, language, showtime_id) for showtime_id, movie_id, screen_id, starts_at, fmt, language in showtimes],
    )

    for user_id, username, display_name, password, role, locked, verified in users:
        salt = f"cinema-demo-{username}"
        connection.execute(
            """
            INSERT OR IGNORE INTO users
            (id, username, display_name, password_hash, password_salt, role, locked, email_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, display_name, hash_password(password, salt), salt, role, locked, verified),
        )

    for screen_id, _, seat_rows, seats_per_row, _ in screens:
        seat_id = screen_id * 1000
        for row_index in range(seat_rows):
            row_label = chr(ord("A") + row_index)
            for seat_number in range(1, seats_per_row + 1):
                seat_id += 1
                seat_code = f"{row_label}{seat_number}"
                seat_type = "vip" if row_index >= seat_rows - 2 else "standard"
                connection.execute(
                    "INSERT OR IGNORE INTO seats VALUES (?, ?, ?, ?, ?, ?)",
                    (seat_id, screen_id, row_label, seat_number, seat_code, seat_type),
                )


def ensure_session(session_id: str) -> None:
    with get_connection() as connection:
        existing = connection.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if existing:
            connection.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now_iso(), session_id))
        else:
            timestamp = now_iso()
            connection.execute("INSERT INTO sessions (session_id, created_at, updated_at) VALUES (?, ?, ?)", (session_id, timestamp, timestamp))


def set_session_user(session_id: str, user_id: Optional[int]) -> None:
    ensure_session(session_id)
    with get_connection() as connection:
        connection.execute("UPDATE sessions SET user_id = ?, updated_at = ? WHERE session_id = ?", (user_id, now_iso(), session_id))


def get_user_by_session(session_id: str) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT users.* FROM users
            JOIN sessions ON sessions.user_id = users.id
            WHERE sessions.session_id = ?
            """,
            (session_id,),
        ).fetchone()


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute("SELECT * FROM users WHERE username = ?", (username.lower().strip(),)).fetchone()


def verify_password(user: sqlite3.Row, password: str) -> bool:
    return secrets.compare_digest(user["password_hash"], hash_password(password, user["password_salt"]))


def fetch_movies(featured_only: bool = False) -> list[sqlite3.Row]:
    query = "SELECT * FROM movies"
    params: tuple[int, ...] = ()
    if featured_only:
        query += " WHERE featured = ?"
        params = (1,)
    query += " ORDER BY featured DESC, title ASC"
    with get_connection() as connection:
        return connection.execute(query, params).fetchall()


def fetch_movie(movie_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute("SELECT * FROM movies WHERE id = ?", (movie_id,)).fetchone()


def fetch_showtimes_for_movie(movie_id: int) -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT showtimes.*, screens.name AS screen_name, screens.format_label, ticket_prices.price_vnd
            FROM showtimes
            JOIN screens ON screens.id = showtimes.screen_id
            JOIN ticket_prices ON ticket_prices.format = showtimes.format
            WHERE showtimes.movie_id = ?
            ORDER BY showtimes.starts_at ASC
            """,
            (movie_id,),
        ).fetchall()


def fetch_upcoming_showtimes(limit: int = 6) -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT showtimes.*, movies.title AS movie_title, screens.name AS screen_name, ticket_prices.price_vnd
            FROM showtimes
            JOIN movies ON movies.id = showtimes.movie_id
            JOIN screens ON screens.id = showtimes.screen_id
            JOIN ticket_prices ON ticket_prices.format = showtimes.format
            ORDER BY showtimes.starts_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def fetch_showtime(showtime_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT showtimes.*, movies.title AS movie_title, movies.genre, movies.rating,
                   movies.duration_minutes, movies.visual_theme, screens.name AS screen_name,
                   screens.format_label, ticket_prices.price_vnd
            FROM showtimes
            JOIN movies ON movies.id = showtimes.movie_id
            JOIN screens ON screens.id = showtimes.screen_id
            JOIN ticket_prices ON ticket_prices.format = showtimes.format
            WHERE showtimes.id = ?
            """,
            (showtime_id,),
        ).fetchone()


def fetch_ticket_prices() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute("SELECT * FROM ticket_prices ORDER BY price_vnd ASC").fetchall()


def expire_old_holds() -> list[sqlite3.Row]:
    timestamp = now_iso()
    with get_connection() as connection:
        expired = connection.execute(
            "SELECT * FROM seat_holds WHERE status = 'held' AND expires_at <= ?",
            (timestamp,),
        ).fetchall()
        connection.execute("UPDATE seat_holds SET status = 'expired' WHERE status = 'held' AND expires_at <= ?", (timestamp,))
        return expired


def fetch_seats_for_showtime(showtime_id: int, session_id: str) -> list[dict]:
    showtime = fetch_showtime(showtime_id)
    if showtime is None:
        return []
    expire_old_holds()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT seats.*,
                   CASE
                     WHEN booking_seats.seat_id IS NOT NULL THEN 'booked'
                     WHEN seat_holds.status = 'held' AND seat_holds.session_id = ? THEN 'held_by_you'
                     WHEN seat_holds.status = 'held' THEN 'held'
                     ELSE 'available'
                   END AS status,
                   seat_holds.expires_at AS hold_expires_at
            FROM seats
            LEFT JOIN booking_seats ON booking_seats.seat_id = seats.id AND booking_seats.showtime_id = ?
            LEFT JOIN seat_holds ON seat_holds.seat_id = seats.id
                 AND seat_holds.showtime_id = ?
                 AND seat_holds.status = 'held'
            WHERE seats.screen_id = ?
            ORDER BY seats.row_label ASC, seats.seat_number ASC
            """,
            (session_id, showtime_id, showtime_id, showtime["screen_id"]),
        ).fetchall()
    return [dict(row) for row in rows]


def addon_prices() -> dict[str, int]:
    return {"popcorn": 55000, "coke": 30000, "combo": 79000, "water": 20000, "nachos": 65000}


def seat_price(showtime: sqlite3.Row, seat: sqlite3.Row) -> int:
    return int(showtime["price_vnd"]) + (30000 if seat["seat_type"] == "vip" else 0)


def create_hold(showtime_id: int, seat_codes: Iterable[str], session_id: str, user_id: int, expire_seconds: Optional[int] = None) -> tuple[str, dict]:
    expire_old_holds()
    normalized = [code.strip().upper() for code in seat_codes if code.strip()]
    if not normalized:
        return "error", {"reason": "no_seats", "message": "Select at least one seat"}
    showtime = fetch_showtime(showtime_id)
    if showtime is None:
        return "error", {"reason": "showtime_not_found", "message": "Showtime not found"}
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expire_seconds or HOLD_MINUTES * 60)).isoformat()
    with get_connection() as connection:
        seats = connection.execute(
            f"SELECT * FROM seats WHERE screen_id = ? AND seat_code IN ({','.join('?' for _ in normalized)})",
            (showtime["screen_id"], *normalized),
        ).fetchall()
        if len(seats) != len(set(normalized)):
            return "error", {"reason": "seat_not_found", "message": "One or more seats do not exist"}
        booked = connection.execute(
            f"SELECT seats.seat_code FROM booking_seats JOIN seats ON seats.id = booking_seats.seat_id WHERE booking_seats.showtime_id = ? AND seats.seat_code IN ({','.join('?' for _ in normalized)})",
            (showtime_id, *normalized),
        ).fetchall()
        if booked:
            return "booked", {"seat_ids": [row["seat_code"] for row in booked], "reason": "already_booked", "message": "Seat already booked"}
        held = connection.execute(
            f"SELECT seats.seat_code, seat_holds.session_id FROM seat_holds JOIN seats ON seats.id = seat_holds.seat_id WHERE seat_holds.showtime_id = ? AND seat_holds.status = 'held' AND seats.seat_code IN ({','.join('?' for _ in normalized)})",
            (showtime_id, *normalized),
        ).fetchall()
        if held:
            same_session = all(row["session_id"] == session_id for row in held)
            return ("double_hold" if same_session else "held"), {"seat_ids": [row["seat_code"] for row in held], "reason": "already_held", "message": "Seat already held"}
        timestamp = now_iso()
        hold_ids = []
        amount = 0
        for seat in seats:
            cursor = connection.execute(
                """
                INSERT INTO seat_holds (showtime_id, seat_id, session_id, user_id, status, created_at, expires_at)
                VALUES (?, ?, ?, ?, 'held', ?, ?)
                """,
                (showtime_id, seat["id"], session_id, user_id, timestamp, expires_at),
            )
            hold_ids.append(cursor.lastrowid)
            amount += seat_price(showtime, seat)
        return "success", {"hold_id": ",".join(str(value) for value in hold_ids), "seat_ids": normalized, "amount": amount, "expires_at": expires_at, "message": "Seats held"}


def release_hold(hold_id: str, session_id: str) -> list[str]:
    ids = [int(value) for value in hold_id.split(",") if value.strip().isdigit()]
    if not ids:
        return []
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT seats.seat_code FROM seat_holds JOIN seats ON seats.id = seat_holds.seat_id WHERE seat_holds.id IN ({','.join('?' for _ in ids)}) AND seat_holds.session_id = ? AND seat_holds.status = 'held'",
            (*ids, session_id),
        ).fetchall()
        connection.execute(
            f"UPDATE seat_holds SET status = 'released' WHERE id IN ({','.join('?' for _ in ids)}) AND session_id = ? AND status = 'held'",
            (*ids, session_id),
        )
        return [row["seat_code"] for row in rows]


def confirm_booking(hold_id: str, session_id: str, user_id: int, addons: Iterable[str], idempotency_key: str) -> tuple[str, dict]:
    expire_old_holds()
    ids = [int(value) for value in hold_id.split(",") if value.strip().isdigit()]
    if not ids:
        return "error", {"reason": "hold_not_found", "message": "Hold not found"}
    with get_connection() as connection:
        duplicate = connection.execute(
            "SELECT id FROM bookings WHERE user_id = ? AND idempotency_key = ?",
            (user_id, idempotency_key),
        ).fetchone()
        if duplicate:
            return "duplicate", {"booking_id": duplicate["id"], "reason": "duplicate_idempotency_key", "message": "Duplicate booking request"}
        holds = connection.execute(
            f"SELECT * FROM seat_holds WHERE id IN ({','.join('?' for _ in ids)}) AND session_id = ?",
            (*ids, session_id),
        ).fetchall()
        if len(holds) != len(ids):
            return "error", {"reason": "hold_not_found", "message": "Hold not found"}
        if any(row["status"] == "expired" for row in holds):
            return "expired", {"reason": "hold_expired", "message": "Hold expired"}
        if any(row["status"] != "held" for row in holds):
            return "error", {"reason": "hold_not_active", "message": "Hold is not active"}
        showtime_id = holds[0]["showtime_id"]
        if any(row["showtime_id"] != showtime_id for row in holds):
            return "error", {"reason": "mixed_showtimes", "message": "Seats must belong to one showtime"}
        conflict = connection.execute(
            f"SELECT seat_id FROM booking_seats WHERE showtime_id = ? AND seat_id IN ({','.join('?' for _ in holds)})",
            (showtime_id, *[row["seat_id"] for row in holds]),
        ).fetchall()
        if conflict:
            return "conflict", {"reason": "seat_conflict", "message": "Seat conflict detected"}
        showtime = fetch_showtime(showtime_id)
        seats = connection.execute(
            f"SELECT * FROM seats WHERE id IN ({','.join('?' for _ in holds)})",
            tuple(row["seat_id"] for row in holds),
        ).fetchall()
        selected_addons = [name for name in addons if name in addon_prices()]
        amount = sum(seat_price(showtime, seat) for seat in seats)
        amount += sum(addon_prices()[name] for name in selected_addons)
        cursor = connection.execute(
            """
            INSERT INTO bookings (showtime_id, user_id, session_id, status, amount, currency, idempotency_key, created_at)
            VALUES (?, ?, ?, 'confirmed', ?, 'VND', ?, ?)
            """,
            (showtime_id, user_id, session_id, amount, idempotency_key, now_iso()),
        )
        booking_id = cursor.lastrowid
        for hold in holds:
            connection.execute("INSERT INTO booking_seats VALUES (?, ?, ?)", (booking_id, hold["seat_id"], showtime_id))
        for name in selected_addons:
            connection.execute("INSERT INTO booking_addons VALUES (?, ?, ?, ?)", (booking_id, name, 1, addon_prices()[name]))
        connection.execute(
            f"UPDATE seat_holds SET status = 'booked' WHERE id IN ({','.join('?' for _ in ids)})",
            tuple(ids),
        )
        return "success", {"booking_id": booking_id, "showtime_id": showtime_id, "seat_ids": [seat["seat_code"] for seat in seats], "amount": amount, "currency": "VND", "message": "Booking confirmed"}


def fetch_booking(booking_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT bookings.*, movies.title AS movie_title, showtimes.starts_at, showtimes.format, screens.name AS screen_name
            FROM bookings
            JOIN showtimes ON showtimes.id = bookings.showtime_id
            JOIN movies ON movies.id = showtimes.movie_id
            JOIN screens ON screens.id = showtimes.screen_id
            WHERE bookings.id = ?
            """,
            (booking_id,),
        ).fetchone()


def fetch_booking_seats(booking_id: int) -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT seats.seat_code FROM booking_seats JOIN seats ON seats.id = booking_seats.seat_id WHERE booking_id = ? ORDER BY seats.seat_code",
            (booking_id,),
        ).fetchall()
        return [row["seat_code"] for row in rows]


def cancel_booking(booking_id: int, user_id: int, admin: bool = False) -> tuple[str, dict]:
    booking = fetch_booking(booking_id)
    if booking is None:
        return "error", {"reason": "booking_not_found", "message": "Booking not found"}
    if not admin and booking["user_id"] != user_id:
        return "error", {"reason": "forbidden", "message": "Cannot cancel this booking"}
    if booking["status"] == "canceled":
        return "error", {"reason": "already_canceled", "message": "Booking already canceled"}
    seat_ids = fetch_booking_seats(booking_id)
    with get_connection() as connection:
        connection.execute("UPDATE bookings SET status = 'canceled', canceled_at = ? WHERE id = ?", (now_iso(), booking_id))
        connection.execute("DELETE FROM booking_seats WHERE booking_id = ?", (booking_id,))
    return "success", {"booking_id": booking_id, "seat_ids": seat_ids, "amount": booking["amount"], "message": "Booking canceled"}


def admin_stats() -> dict:
    with get_connection() as connection:
        return {
            "movies": connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0],
            "showtimes": connection.execute("SELECT COUNT(*) FROM showtimes").fetchone()[0],
            "bookings": connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
            "revenue": connection.execute("SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE status = 'confirmed'").fetchone()[0],
            "recent": connection.execute(
                """
                SELECT bookings.id, bookings.status, bookings.amount, bookings.created_at, movies.title AS movie_title
                FROM bookings
                JOIN showtimes ON showtimes.id = bookings.showtime_id
                JOIN movies ON movies.id = showtimes.movie_id
                ORDER BY bookings.created_at DESC
                LIMIT 8
                """
            ).fetchall(),
        }


def record_admin_event(event: str, user_id: int, message: str) -> None:
    with get_connection() as connection:
        connection.execute("INSERT INTO admin_events (event, user_id, message, created_at) VALUES (?, ?, ?, ?)", (event, user_id, message, now_iso()))


def run_admin_action(event: str, user_id: int) -> str:
    messages = {
        "movie_created": "Created demo midnight premiere movie",
        "movie_updated": "Updated featured movie metadata",
        "movie_deleted": "Deleted archived demo movie",
        "showtime_created": "Created late-night demo showtime",
        "showtime_updated": "Updated demo showtime language",
        "showtime_deleted": "Deleted canceled demo showtime",
        "pricing_updated": "Updated 2D ticket price by 5,000 VND",
        "seatmap_updated": "Marked demo seat map refresh",
        "manual_booking_created": "Created manual box-office booking",
        "manual_booking_canceled": "Canceled manual box-office booking",
    }
    message = messages.get(event, "Admin demo action completed")
    with get_connection() as connection:
        if event == "pricing_updated":
            connection.execute("UPDATE ticket_prices SET price_vnd = price_vnd + 5000 WHERE format = '2D'")
        elif event == "movie_updated":
            connection.execute("UPDATE movies SET featured = 1 WHERE id = 4")
        connection.execute("INSERT INTO admin_events (event, user_id, message, created_at) VALUES (?, ?, ?, ?)", (event, user_id, message, now_iso()))
    return message
