Chạy docker:
```bash
cd infra
docker compose up -d
```
Chạy simulator:
```bash
python sim/simulator.py
```
Truy cập vào https://localhost:3000
Đăng nhập với username: admin, password: admin (xong rồi chọn skip)

Bên menu bên trái phần `Connections` chọn `Data sources` rồi chọn `Add data source` và chọn `Loki` rồi điền URL là `http://loki:3100` rồi chọn `Save & Test` để kết nối với Loki.

Sau đó vào phần `Explore`, chọn `Loki`. Phần `Label filter` chọn `job` rồi chọn `payment_gateway` để xem log của payment gateway.

Rồi cuối cùng chọn `Run query` hoặc `Live` để xem.

```