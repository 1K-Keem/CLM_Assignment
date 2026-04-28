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
                featured INTEGER NOT NULL DEFAULT 0,
                poster_url TEXT,
                backdrop_url TEXT
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
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(movies)").fetchall()}
        if "poster_url" not in columns:
            connection.execute("ALTER TABLE movies ADD COLUMN poster_url TEXT")
        if "backdrop_url" not in columns:
            connection.execute("ALTER TABLE movies ADD COLUMN backdrop_url TEXT")
        seed_database(connection)


def seed_database(connection: sqlite3.Connection) -> None:
    movies = [
        (1, "Bo Gia", "bo-gia", "Gia dinh, hai, chinh kich", "C13", 128, "Bo Gia là phim Việt Nam thuộc thể loại gia dinh, hai, chinh kich, do Tran Thanh, Vu Ngoc Dang đạo diễn. Phim phát hành năm 2021.", "Tran Thanh, Tuan Tran, Ngan Chi, Ngoc Giau, Le Giang, Lan Phuong", "signal", 1, "/static/posters/bo-gia-poster.jpg", "/static/posters/bo-gia-backdrop.jpg"),
        (2, "Bo tu bao thu", "bo-tu-bao-thu", "Hai, tinh cam", "T16", 132, "Bo tu bao thu là phim Việt Nam thuộc thể loại hai, tinh cam, do Tran Thanh đạo diễn. Phim phát hành năm 2025.", "Tieu Vy, Quoc Anh, Ky Duyen, Le Duong Bao Lam, Le Giang, Uyen An, Tran Thanh", "neon", 1, "/static/posters/bo-tu-bao-thu-poster.jpg", "/static/posters/bo-tu-bao-thu-backdrop.jpg"),
        (3, "Cua lai vo bau", "cua-lai-vo-bau", "Hai, tinh cam, chinh kich", "T13", 100, "Cua lai vo bau là phim Việt Nam thuộc thể loại hài, tình cảm và chính kịch, phù hợp cho suất chiếu cuối tuần.", "Tran Thanh, Ninh Duong Lan Ngoc, Anh Tu, Le Giang, Hoai Linh", "lantern", 1, "/static/posters/cua-lai-vo-bau-poster.jpg", "/static/posters/cua-lai-vo-bau-backdrop.jpg"),
        (4, "Hai Phuong", "hai-phuong", "Hanh dong, vo thuat", "C18", 98, "Hai Phuong là phim hành động Việt Nam có tiết tấu nhanh, kể hành trình người mẹ đối đầu đường dây bắt cóc.", "Ngo Thanh Van, Mai Cat Vy, Phan Thanh Nhien, Pham Anh Khoa", "apricot", 1, "/static/posters/hai-phuong-poster.jpg", "/static/posters/hai-phuong-backdrop.jpg"),
        (5, "Ke an hon", "ke-an-hon", "Kinh di", "T18", 109, "Ke an hon là phim kinh dị Việt Nam, phù hợp để demo các suất chiếu đêm và hành vi đặt vé cao điểm.", "Hoang Ha, Vo Dien Gia Huy, Huynh Thanh Truc, Lan Phuong", "orbit", 1, "/static/posters/ke-an-hon-poster.jpg", "/static/posters/ke-an-hon-backdrop.jpg"),
        (6, "Lac gioi", "lac-gioi", "Tinh cam, tam ly, chinh kich", "C16", 96, "Lac gioi là phim tâm lý Việt Nam khai thác những mối quan hệ phức tạp và lựa chọn cá nhân.", "Trung Dung, Mai Thu Huyen, Binh An, Thanh Loc, My Uyen", "signal", 1, "/static/posters/lac-gioi-poster.jpg", "/static/posters/lac-gioi-backdrop.jpg"),
        (7, "Mai", "mai", "Tam ly, tinh cam, chinh kich", "T18", 131, "Mai là phim Việt Nam về một người phụ nữ đi qua tổn thương, cô đơn và lựa chọn yêu thương chính mình.", "Phuong Anh Dao, Tuan Tran, Tran Thanh, Hong Dao, Ngoc Giau", "neon", 1, "/static/posters/mai-poster.jpg", "/static/posters/mai-backdrop.jpg"),
        (8, "Mua do", "mua-do", "Lich su, chien tranh, chinh kich", "T16", 124, "Mua do là phim lịch sử chiến tranh Việt Nam, phù hợp cho cụm phim đặc biệt và suất chiếu chuyên đề.", "Do Nhat Hoang, Le Ha Anh, Steven Nguyen, Hua Vi Van, Lam Thanh Nha", "lantern", 1, "/static/posters/mua-do-poster.jpg", "/static/posters/mua-do-backdrop.jpg"),
        (9, "Nha Ba Nu", "nha-ba-nu", "Tam ly, gia dinh, chinh kich", "T16", 102, "Nha Ba Nu là câu chuyện gia đình đô thị nhiều xung đột, phù hợp cho nhóm khán giả đi xem cuối tuần.", "Le Giang, Uyen An, Song Luan, Tran Thanh, Ngoc Giau, Viet Anh", "apricot", 0, "/static/posters/nha-ba-nu-poster.jpg", "/static/posters/nha-ba-nu-backdrop.png"),
        (10, "Tham tu Kien: Ky an khong dau", "tham-tu-kien-ky-an-khong-dau", "Trinh tham, giat gan, kinh di", "T16", 120, "Tham tu Kien: Ky an khong dau là phim trinh thám pha màu kinh dị, phù hợp cho lịch chiếu tối.", "Quoc Huy, Dinh Ngoc Diep, cac dien vien khac", "orbit", 0, "/static/posters/tham-tu-kien-ky-an-khong-dau-poster.jpg", "/static/posters/tham-tu-kien-ky-an-khong-dau-backdrop.jpg"),
        (11, "Tu chien tren khong", "tu-chien-tren-khong", "Hanh dong, lich su, toi pham, giat gan, chinh kich", "T16", 118, "Tu chien tren khong là phim hành động lịch sử với nhịp căng thẳng, phù hợp cho suất chiếu IMAX/VIP demo.", "Thai Hoa, Kaity Nguyen, Thanh Son, Vo Dien Gia Huy, Tran Ngoc Vang", "signal", 0, "/static/posters/tu-chien-tren-khong-poster.jpg", "/static/posters/tu-chien-tren-khong-backdrop.jpg"),
        (12, "The Shawshank Redemption", "the-shawshank-redemption", "Chính kịch", "T16", 142, "The Shawshank Redemption là phim nổi bật trong bộ sưu tập 30 phim, phù hợp cho lịch chiếu chuyên đề tại CLM Cinema.", "Tim Robbins, Morgan Freeman, Bob Gunton, William Sadler", "neon", 0, "/static/posters/the-shawshank-redemption-poster.jpg", "/static/posters/the-shawshank-redemption-poster.jpg"),
        (13, "The Godfather", "the-godfather", "Tội phạm, chính kịch", "T18", 175, "The Godfather là phim kinh điển về gia đình mafia Corleone, phù hợp cho chuyên đề điện ảnh kinh điển.", "Marlon Brando, Al Pacino, James Caan, Diane Keaton", "lantern", 0, "/static/posters/the-godfather-poster.jpg", "/static/posters/the-godfather-poster.jpg"),
        (14, "The Godfather Part II", "the-godfather-part-ii", "Tội phạm, chính kịch", "T18", 202, "The Godfather Part II tiếp nối câu chuyện gia đình Corleone với quy mô sử thi và chính kịch sâu.", "Al Pacino, Robert De Niro, Robert Duvall, Diane Keaton", "apricot", 0, "/static/posters/the-godfather-part-ii-poster.jpg", "/static/posters/the-godfather-part-ii-poster.jpg"),
        (15, "The Dark Knight", "the-dark-knight", "Hành động, tội phạm", "T16", 152, "The Dark Knight là phim siêu anh hùng tội phạm nổi bật, phù hợp cho lịch chiếu đêm và định dạng lớn.", "Christian Bale, Heath Ledger, Aaron Eckhart, Michael Caine", "orbit", 0, "/static/posters/the-dark-knight-poster.jpg", "/static/posters/the-dark-knight-poster.jpg"),
        (16, "Schindler's List", "schindler-s-list", "Chính kịch, lịch sử", "T16", 195, "Schindler's List là phim chính kịch lịch sử kinh điển, phù hợp cho suất chiếu chuyên đề.", "Liam Neeson, Ben Kingsley, Ralph Fiennes", "signal", 0, "/static/posters/schindler-s-list-poster.jpg", "/static/posters/schindler-s-list-poster.jpg"),
        (17, "Pulp Fiction", "pulp-fiction", "Tội phạm, hài đen", "T18", 154, "Pulp Fiction là phim tội phạm hài đen có cấu trúc phi tuyến, phù hợp cho bộ sưu tập phim kinh điển.", "John Travolta, Uma Thurman, Samuel L. Jackson, Bruce Willis", "neon", 0, "/static/posters/pulp-fiction-poster.jpg", "/static/posters/pulp-fiction-poster.jpg"),
        (18, "The Lord of the Rings: The Return of the King", "the-lord-of-the-rings-the-return-of-the-king", "Phiêu lưu, giả tưởng", "T13", 201, "The Return of the King là phần kết sử thi của Chúa Nhẫn, phù hợp cho marathon cuối tuần.", "Elijah Wood, Viggo Mortensen, Ian McKellen, Sean Astin", "lantern", 0, "/static/posters/the-lord-of-the-rings-the-return-of-the-king-poster.jpg", "/static/posters/the-lord-of-the-rings-the-return-of-the-king-poster.jpg"),
        (19, "The Lord of the Rings: The Fellowship of the Ring", "the-lord-of-the-rings-the-fellowship-of-the-ring", "Phiêu lưu, giả tưởng", "T13", 178, "The Fellowship of the Ring mở đầu hành trình Trung Địa, phù hợp cho suất chiếu chuyên đề giả tưởng.", "Elijah Wood, Ian McKellen, Viggo Mortensen, Sean Astin", "apricot", 0, "/static/posters/the-lord-of-the-rings-the-fellowship-of-the-ring-poster.jpg", "/static/posters/the-lord-of-the-rings-the-fellowship-of-the-ring-poster.jpg"),
        (20, "The Lord of the Rings: The Two Towers", "the-lord-of-the-rings-the-two-towers", "Phiêu lưu, giả tưởng", "T13", 179, "The Two Towers tiếp tục cuộc chiến Trung Địa, phù hợp cho lịch chiếu marathon.", "Elijah Wood, Ian McKellen, Viggo Mortensen, Orlando Bloom", "orbit", 0, "/static/posters/the-lord-of-the-rings-the-two-towers-poster.jpg", "/static/posters/the-lord-of-the-rings-the-two-towers-poster.jpg"),
        (21, "Inception", "inception", "Khoa học viễn tưởng, hành động", "T13", 148, "Inception là phim khoa học viễn tưởng về giấc mơ và ký ức, hợp cho suất chiếu định dạng lớn.", "Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page, Tom Hardy", "signal", 0, "/static/posters/inception-poster.jpg", "/static/posters/inception-poster.jpg"),
        (22, "Interstellar", "interstellar", "Khoa học viễn tưởng, phiêu lưu", "T13", 169, "Interstellar là chuyến du hành không gian giàu cảm xúc, phù hợp cho lịch chiếu IMAX demo.", "Matthew McConaughey, Anne Hathaway, Jessica Chastain, Michael Caine", "neon", 0, "/static/posters/interstellar-poster.jpg", "/static/posters/interstellar-poster.jpg"),
        (23, "Fight Club", "fight-club", "Tâm lý, tội phạm", "T18", 139, "Fight Club là phim tâm lý tội phạm nổi bật, phù hợp cho cụm phim cult classic.", "Brad Pitt, Edward Norton, Helena Bonham Carter, Meat Loaf", "lantern", 0, "/static/posters/fight-club-poster.jpg", "/static/posters/fight-club-poster.jpg"),
        (24, "Forrest Gump", "forrest-gump", "Chính kịch, hài lãng mạn", "T13", 142, "Forrest Gump là hành trình cuộc đời giàu cảm xúc, phù hợp cho suất chiếu gia đình.", "Tom Hanks, Robin Wright, Gary Sinise, Sally Field", "apricot", 0, "/static/posters/forrest-gump-poster.jpg", "/static/posters/forrest-gump-poster.jpg"),
        (25, "Parasite", "parasite", "Chính kịch, giật gân", "T16", 132, "Parasite là phim chính kịch giật gân Hàn Quốc, phù hợp cho suất chiếu điện ảnh châu Á.", "Song Kang-ho, Lee Sun-kyun, Cho Yeo-jeong, Park So-dam", "orbit", 0, "/static/posters/parasite-poster.jpg", "/static/posters/parasite-poster.jpg"),
        (26, "Spirited Away", "spirited-away", "Hoạt hình, giả tưởng", "T13", 125, "Spirited Away là phim hoạt hình giả tưởng kinh điển, phù hợp cho khán giả gia đình.", "Rumi Hiiragi, Miyu Irino, Mari Natsuki, Takashi Naito", "signal", 0, "/static/posters/spirited-away-poster.jpg", "/static/posters/spirited-away-poster.jpg"),
        (27, "The Matrix", "the-matrix", "Khoa học viễn tưởng, hành động", "T16", 136, "The Matrix là phim hành động khoa học viễn tưởng kinh điển, phù hợp cho suất chiếu đêm.", "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss, Hugo Weaving", "neon", 0, "/static/posters/the-matrix-poster.jpg", "/static/posters/the-matrix-poster.jpg"),
        (28, "Goodfellas", "goodfellas", "Tội phạm, chính kịch", "T18", 146, "Goodfellas là phim tội phạm chính kịch kinh điển, phù hợp cho chuyên đề điện ảnh Mỹ.", "Ray Liotta, Robert De Niro, Joe Pesci, Lorraine Bracco", "lantern", 0, "/static/posters/goodfellas-poster.jpg", "/static/posters/goodfellas-poster.jpg"),
        (29, "Se7en", "se7en", "Tội phạm, giật gân", "T18", 127, "Se7en là phim tội phạm giật gân u tối, phù hợp cho suất chiếu thriller đêm.", "Brad Pitt, Morgan Freeman, Gwyneth Paltrow, Kevin Spacey", "apricot", 0, "/static/posters/se7en-poster.jpg", "/static/posters/se7en-poster.jpg"),
        (30, "The Silence of the Lambs", "the-silence-of-the-lambs", "Tội phạm, kinh dị", "T18", 118, "The Silence of the Lambs là phim tội phạm kinh dị kinh điển, phù hợp cho lịch chiếu thriller.", "Jodie Foster, Anthony Hopkins, Scott Glenn, Ted Levine", "orbit", 0, "/static/posters/the-silence-of-the-lambs-poster.jpg", "/static/posters/the-silence-of-the-lambs-poster.jpg"),
        (31, "Saving Private Ryan", "saving-private-ryan", "Chiến tranh, chính kịch", "T18", 169, "Saving Private Ryan là phim chiến tranh chính kịch nổi bật, phù hợp cho suất chiếu chuyên đề.", "Tom Hanks, Matt Damon, Tom Sizemore, Edward Burns", "signal", 0, "/static/posters/saving-private-ryan-poster.jpg", "/static/posters/saving-private-ryan-poster.jpg"),
        (32, "Whiplash", "whiplash", "Chính kịch, âm nhạc", "T16", 106, "Whiplash là phim chính kịch âm nhạc căng thẳng, phù hợp cho suất chiếu nghệ thuật.", "Miles Teller, J. K. Simmons, Paul Reiser, Melissa Benoist", "neon", 0, "/static/posters/whiplash-poster.jpg", "/static/posters/whiplash-poster.jpg"),
        (33, "La La Land", "la-la-land", "Nhạc kịch, lãng mạn", "T13", 128, "La La Land là phim nhạc kịch lãng mạn hiện đại, phù hợp cho suất chiếu couple night.", "Ryan Gosling, Emma Stone, John Legend, Rosemarie DeWitt", "lantern", 0, "/static/posters/la-la-land-poster.jpg", "/static/posters/la-la-land-poster.jpg"),
        (34, "Inside Out", "inside-out", "Hoạt hình, gia đình", "T13", 95, "Inside Out là phim hoạt hình gia đình về cảm xúc, phù hợp cho suất chiếu thiếu nhi.", "Amy Poehler, Phyllis Smith, Bill Hader, Lewis Black", "apricot", 0, "/static/posters/inside-out-poster.jpg", "/static/posters/inside-out-poster.jpg"),
        (35, "Coco", "coco", "Hoạt hình, âm nhạc", "T13", 105, "Coco là phim hoạt hình âm nhạc giàu cảm xúc, phù hợp cho khán giả gia đình.", "Anthony Gonzalez, Gael Garcia Bernal, Benjamin Bratt, Alanna Ubach", "orbit", 0, "/static/posters/coco-poster.jpg", "/static/posters/coco-poster.jpg"),
        (36, "The Lion King", "the-lion-king", "Hoạt hình, gia đình", "T13", 88, "The Lion King là phim hoạt hình gia đình kinh điển, phù hợp cho suất chiếu cuối tuần.", "Matthew Broderick, James Earl Jones, Jeremy Irons, Nathan Lane", "signal", 0, "/static/posters/the-lion-king-poster.jpg", "/static/posters/the-lion-king-poster.jpg"),
        (37, "Gladiator", "gladiator", "Hành động, sử thi", "T16", 155, "Gladiator là phim hành động sử thi nổi bật, phù hợp cho suất chiếu màn hình lớn.", "Russell Crowe, Joaquin Phoenix, Connie Nielsen, Oliver Reed", "neon", 0, "/static/posters/gladiator-poster.jpg", "/static/posters/gladiator-poster.jpg"),
        (38, "Titanic", "titanic", "Lãng mạn, thảm họa", "T13", 195, "Titanic là phim lãng mạn thảm họa kinh điển, phù hợp cho suất chiếu đặc biệt.", "Leonardo DiCaprio, Kate Winslet, Billy Zane, Kathy Bates", "lantern", 0, "/static/posters/titanic-poster.jpg", "/static/posters/titanic-poster.jpg"),
        (39, "Toy Story", "toy-story", "Hoạt hình, gia đình", "T13", 81, "Toy Story là phim hoạt hình gia đình kinh điển, phù hợp cho suất chiếu thiếu nhi.", "Tom Hanks, Tim Allen, Don Rickles, Wallace Shawn", "apricot", 0, "/static/posters/toy-story-poster.jpg", "/static/posters/toy-story-poster.jpg"),
        (40, "Avengers: Endgame", "avengers-endgame", "Siêu anh hùng, hành động", "T13", 181, "Avengers: Endgame là phim siêu anh hùng hành động quy mô lớn, phù hợp cho suất chiếu IMAX.", "Robert Downey Jr., Chris Evans, Mark Ruffalo, Chris Hemsworth", "orbit", 0, "/static/posters/avengers-endgame-poster.jpg", "/static/posters/avengers-endgame-poster.jpg"),
        (41, "Spider-Man: Into the Spider-Verse", "spider-man-into-the-spider-verse", "Hoạt hình, siêu anh hùng", "T13", 117, "Spider-Man: Into the Spider-Verse là phim hoạt hình siêu anh hùng giàu phong cách thị giác.", "Shameik Moore, Jake Johnson, Hailee Steinfeld, Mahershala Ali", "signal", 0, "/static/posters/spider-man-into-the-spider-verse-poster.jpg", "/static/posters/spider-man-into-the-spider-verse-poster.jpg"),
        (42, "Avatar", "avatar", "Khoa học viễn tưởng, phiêu lưu", "T13", 162, "Avatar là phim khoa học viễn tưởng phiêu lưu quy mô lớn, phù hợp cho suất chiếu màn hình lớn.", "Sam Worthington, Zoe Saldana, Sigourney Weaver, Stephen Lang", "neon", 0, "/static/posters/avatar-poster.jpg", "/static/posters/avatar-poster.jpg"),
        (43, "Transformers", "transformers", "Hành động, khoa học viễn tưởng", "T13", 144, "Transformers là phim hành động khoa học viễn tưởng, phù hợp cho suất chiếu giải trí cuối tuần.", "Shia LaBeouf, Megan Fox, Josh Duhamel, Tyrese Gibson", "lantern", 0, "/static/posters/transformers-poster.jpg", "/static/posters/transformers-poster.jpg"),
        (44, "Pacific Rim", "pacific-rim", "Khoa học viễn tưởng, hành động", "T13", 131, "Pacific Rim là phim khoa học viễn tưởng hành động về Jaeger và Kaiju, phù hợp cho suất chiếu màn hình lớn.", "Charlie Hunnam, Idris Elba, Rinko Kikuchi, Charlie Day", "apricot", 0, "/static/posters/pacific-rim-poster.jpg", "/static/posters/pacific-rim-poster.jpg"),
    ]
    screens = [
        (1, "Cinestar Sinh Viên", 7, 10, "Khu đô thị Đại học Quốc Gia TP.HCM"),
        (2, "Cinestar Quốc Thanh", 6, 8, "Nguyễn Trãi, Quận 1, TP.HCM"),
        (3, "CGV Vincom Đồng Khởi", 7, 9, "Vincom Center Đồng Khởi, Quận 1, TP.HCM"),
        (4, "Galaxy Nguyễn Du", 6, 9, "Nguyễn Du, Quận 1, TP.HCM"),
    ]
    prices = [("2D", 95000), ("3D", 125000), ("IMAX", 175000), ("VIP", 230000)]
    formats = ["2D", "VIP", "IMAX", "3D"]
    showtimes = []
    first_showtime = datetime(2026, 5, 1, 9, 30)
    for index, movie in enumerate(movies):
        movie_id = movie[0]
        for offset in range(3):
            showtime_id = movie_id * 100 + offset + 1
            screen_id = screens[(index + offset) % len(screens)][0]
            starts_at = first_showtime + timedelta(days=index // 8, hours=(index * 2 + offset * 4) % 13, minutes=15 * (index % 4))
            showtimes.append((showtime_id, movie_id, screen_id, starts_at.isoformat(), formats[(index + offset) % len(formats)], "Phụ đề / thuyết minh tuỳ suất"))
    showtimes[0] = (101, 1, 1, "2026-05-01T18:30:00", "2D", "Tiếng Việt")
    users = [
        (1, "user@example.com", "Demo User", "demo123", "customer", 0, 1),
        (2, "admin@example.com", "Admin User", "admin123", "admin", 0, 1),
        (3, "locked@example.com", "Locked User", "locked123", "customer", 1, 0),
    ]

    connection.executemany("INSERT OR IGNORE INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", movies)
    connection.executemany(
        """
        UPDATE movies
        SET title = ?, slug = ?, genre = ?, rating = ?, duration_minutes = ?, synopsis = ?,
            cast = ?, visual_theme = ?, featured = ?,
            poster_url = ?,
            backdrop_url = ?
        WHERE id = ?
        """,
        [(title, slug, genre, rating, duration, synopsis, cast, theme, featured, poster, backdrop, movie_id) for movie_id, title, slug, genre, rating, duration, synopsis, cast, theme, featured, poster, backdrop in movies],
    )
    connection.executemany("INSERT OR IGNORE INTO screens VALUES (?, ?, ?, ?, ?)", screens)
    connection.executemany(
        "UPDATE screens SET name = ?, seat_rows = ?, seats_per_row = ?, format_label = ? WHERE id = ?",
        [(name, rows, seats, label, screen_id) for screen_id, name, rows, seats, label in screens],
    )
    connection.executemany("INSERT OR IGNORE INTO ticket_prices VALUES (?, ?)", prices)
    connection.executemany("UPDATE ticket_prices SET price_vnd = ? WHERE format = ?", [(price, fmt) for fmt, price in prices])
    movie_ids = [movie[0] for movie in movies]
    showtime_ids = [showtime[0] for showtime in showtimes]
    connection.execute(
        f"DELETE FROM showtimes WHERE id NOT IN ({','.join('?' for _ in showtime_ids)})",
        showtime_ids,
    )
    connection.execute(
        f"DELETE FROM movies WHERE id NOT IN ({','.join('?' for _ in movie_ids)})",
        movie_ids,
    )
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
