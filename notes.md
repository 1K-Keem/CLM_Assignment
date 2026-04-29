# Ghi chú cải tiến CLM

Các thay đổi lần này tập trung vào chất lượng Centralized Log Management, không thêm tính năng mới.

- Request log được phân loại rõ hơn: `request_success` chỉ dành cho 2xx/3xx, `endpoint_not_found` cho 404, `request_rejected` cho 4xx khác, và `request_failed` cho 5xx.
- JSON Lines dễ đọc và phù hợp tiếng Việt hơn nhờ `ensure_ascii=False`; log mới giữ cả `env` và `environment` để không phá tài liệu hoặc log cũ.
- Loki labels vẫn giữ low-cardinality: `job`, `service`, `log_type`, `env`; các giá trị dễ bùng nổ như `request_id`, `session_id`, `user_id`, `booking_id`, `seat_id` chỉ nằm trong JSON body.
- Booking flow có thêm `booking_flow_id` để nối chuỗi `seatmap_viewed`, `seat_hold_requested`, `seat_hold_success`, `booking_requested`, `booking_confirmed`, `booking_success`, và các lỗi booking liên quan.
- `docs/test-scenarios.md` có thêm playbook điều tra sự cố cho auth failure, seat conflict, hold expired, duplicate booking, slow request, và admin audit, kèm LogQL dùng `| json`.
