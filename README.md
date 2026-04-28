# Centralized Log Management

Đây là một dự án về **quản lý nhật ký tập trung** mô phỏng ứng dụng đặt vé xem phim. Hệ thống được xây dựng để mô phỏng một luồng nghiệp vụ thực tế và sinh log có cấu trúc, sau đó gom về Loki để truy vấn và hiển thị trên Grafana.

## Mục tiêu

- Tìm hiểu mô hình centralized log management.
- Triển khai một stack mã nguồn mở để thu thập, lưu trữ và truy vấn log.
- Tạo các kịch bản demo để thử nghiệm, quan sát và đánh giá log.

## Công nghệ sử dụng

- **FastAPI**: ứng dụng web chính.
- **SQLite**: lưu dữ liệu nghiệp vụ cục bộ.
- **JSON Lines**: định dạng log được ứng dụng ghi ra file.
- **Grafana Alloy**: đọc các file log và chuyển tiếp sang Loki.
- **Loki**: lưu trữ và truy vấn log.
- **Grafana**: trực quan hóa và tra cứu log.

## Kiến trúc tổng quan

Luồng xử lý chính của hệ thống:

1. Người dùng thao tác trên ứng dụng FastAPI.
2. Middleware gán `request_id` và `session_id` cho từng request.
3. Ứng dụng ghi log theo từng nhóm vào thư mục `logs/`.
4. Grafana Alloy đọc các file log này và đẩy sang Loki.
5. Grafana truy vấn Loki để xem log theo service, loại log và thời gian.

Tham khảo thêm phần mô tả chi tiết trong [docs/architecture.md](docs/architecture.md).

## Cấu trúc log

Ứng dụng ghi log dạng JSON Lines, mỗi dòng là một JSON object. Các file log chính gồm:

- `logs/app.log`: log request, browse và admin.
- `logs/auth.log`: log đăng nhập, đăng xuất, xác thực và reset mật khẩu.
- `logs/booking.log`: log ghế, giữ chỗ, đặt vé, hủy vé và thêm dịch vụ.
- `logs/error.log`: lỗi bất thường của ứng dụng.
- `logs/payment.log`: log mô phỏng từ payment simulator.

Các trường quan trọng thường có trong log:

- `timestamp`
- `level`
- `service`
- `environment`
- `event`
- `category`
- `request_id`
- `session_id`
- `user_id`

Danh mục event chi tiết nằm trong [docs/log-catalog.md](docs/log-catalog.md).

## Chạy ứng dụng

### 1. Cài đặt phụ thuộc

```bash
python -m pip install -r app/requirements.txt
```

### 2. Khởi tạo dữ liệu demo

```bash
python -m app.seed
```

### 3. Chạy FastAPI

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Sau khi chạy, mở:

- Ứng dụng: `http://127.0.0.1:8000`

## Chạy stack quan sát log

Grafana, Loki và Alloy được cấu hình bằng Docker Compose trong thư mục `infra/`.

```bash
cd infra
docker compose up -d
```

Sau khi chạy xong, truy cập:

- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`

> Lưu ý: stack này chỉ là tầng observability. Ứng dụng FastAPI vẫn chạy riêng bên ngoài Docker Compose.

## Cấu hình Grafana lần đầu

1. Đăng nhập Grafana bằng tài khoản mặc định của image Docker, thường là `admin / admin`.
2. Vào **Connections** -> **Data sources** -> **Add data source**.
3. Chọn **Loki**.
4. Nhập URL: `http://loki:3100`
5. Chọn **Save & Test**.

Sau đó vào **Explore** để truy vấn log.

## Chạy payment simulator

Simulator tạo thêm log giả lập cho hệ thống thanh toán:

```bash
python sim/simulator.py
```

File log sinh ra sẽ được Alloy đọc từ `logs/payment.log` và gắn label `job="payment_gateway"`.

## Tài khoản demo

Các tài khoản demo được nạp từ dữ liệu seed:

- Customer: `user@example.com` / `demo123`
- Admin: `admin@example.com` / `admin123`
- Locked user: `locked@example.com` / `locked123`

## Kịch bản thử nghiệm gợi ý

- Đăng nhập thành công và thất bại.
- Xem danh sách phim và chi tiết phim.
- Giữ ghế, đặt vé, hủy vé.
- Kịch bản lỗi: 404, timeout, rate limit, hold hết hạn.
- Thao tác quản trị như cập nhật giá.
- Quan sát log payment từ simulator.

Chi tiết các luồng test và câu lệnh demo nằm trong [docs/test-scenarios.md](docs/test-scenarios.md).

## Truy vấn mẫu trong Grafana Loki

```logql
{service="movie-ticket-web"}
{service="movie-ticket-web",log_type="auth"} |= "login_failed"
{service="movie-ticket-web",log_type="booking"} |= "booking_failed"
{service="movie-ticket-web",log_type="booking"} |= "seat_hold_expired"
{service="payment_gateway"}
sum by (log_type) (count_over_time({service="movie-ticket-web"}[5m]))
```

## Giới hạn của demo

- Đây là hệ thống demo, chưa phải production.
- Hold ghế hết hạn được xử lý trong luồng request bình thường, không dùng background worker.
- Dữ liệu lưu bằng SQLite cục bộ.
- Rate limit và session management đều ở mức đơn giản để phục vụ bài tập.

## Cấu trúc thư mục chính

```text
app/            # Ứng dụng FastAPI, database, logging và static/templates
docs/           # Tài liệu kiến trúc, log catalog và test scenarios
infra/          # Docker Compose, Alloy và Loki
logs/           # File log JSON Lines được sinh ra khi chạy ứng dụng
sim/            # Payment simulator
```

## Tài liệu

- [docs/architecture.md](docs/architecture.md)
- [docs/log-catalog.md](docs/log-catalog.md)
- [docs/test-scenarios.md](docs/test-scenarios.md)