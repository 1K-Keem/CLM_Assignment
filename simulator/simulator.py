import json
import time
import random
from datetime import datetime

class PaymentGatewaySimulator:
    def __init__(self, log_file_path):
        self.log_file = log_file_path
        self.providers = ["Momo", "ZaloPay", "VNPay", "ShopeePay"]
        self.endpoints = ["/api/checkout", "/api/apply_voucher", "/v1/create_order"]
        
    def _write_to_file(self, log_data):
        """Hàm nội bộ: Thêm timestamp và ghi đè JSON vào file log"""
        # Sinh thời gian chuẩn ISO 8601 (chuẩn tốt nhất cho Loki)
        log_data["timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data) + "\n")
            
        # In ra màn hình console để bạn dễ theo dõi
        print(f"[{log_data['level']}] Bắn log sự kiện: {log_data['event']}")

    def generate_business_log(self):
        """Nhóm 1: Sinh log Giao dịch bình thường"""
        events = [
            {"level": "INFO", "event": "payment_init", "order_id": f"ORD-{random.randint(1000, 9999)}", "amount": random.randint(30, 200) * 1000, "method": random.choice(self.providers)},
            {"level": "INFO", "event": "voucher_apply", "code": "FREESHIP50", "status": "success", "discount": 15000},
            {"level": "INFO", "event": "payment_success", "order_id": f"ORD-{random.randint(1000, 9999)}", "processing_time_ms": random.randint(200, 800)}
        ]
        self._write_to_file(random.choice(events))

    def generate_gateway_log(self):
        """Nhóm 2: Sinh log lỗi kết nối Đối tác"""
        events = [
            {"level": "ERROR", "event": "gateway_timeout", "provider": random.choice(self.providers), "endpoint": random.choice(self.endpoints), "latency_ms": random.randint(5000, 8000)},
            {"level": "WARN", "event": "gateway_rejected", "provider": random.choice(self.providers), "reason": "insufficient_balance"}
        ]
        self._write_to_file(random.choice(events))

    def generate_security_log(self):
        """Nhóm 3: Sinh log Bảo mật (Bị spam hoặc tấn công)"""
        fake_ip = f"{random.randint(100, 200)}.{random.randint(10, 99)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
        events = [
            {"level": "WARN", "event": "rate_limit_exceeded", "ip": fake_ip, "requests_per_sec": random.randint(20, 50)},
            {"level": "CRITICAL", "event": "brute_force_detected", "user_id": f"U-{random.randint(100, 999)}", "reason": "multiple_failed_otp"}
        ]
        self._write_to_file(random.choice(events))

    def generate_system_log(self):
        """Nhóm 4: Sinh log Lỗi Hệ thống"""
        events = [
            {"level": "ERROR", "event": "db_connection_pool", "status": "exhausted", "active_connections": random.randint(200, 250)},
            {"level": "FATAL", "event": "app_crash", "exception": "NullPointerException"}
        ]
        self._write_to_file(random.choice(events))

    def run_simulation(self):
        """Hàm chính: Chạy vòng lặp vô hạn để sinh log ngẫu nhiên"""
        print("🚀 Bắt đầu giả lập Cổng thanh toán. Nhấn Ctrl+C để dừng.\n")
        try:
            while True:
                # Tỷ lệ xuất hiện log (Business xuất hiện nhiều nhất, lỗi xuất hiện ít hơn)
                choice = random.choices(
                    [self.generate_business_log, self.generate_gateway_log, self.generate_security_log, self.generate_system_log],
                    weights=[60, 20, 10, 10], # 60% là log bình thường, 40% là các loại lỗi
                    k=1
                )[0]
                
                choice() # Gọi hàm sinh log
                
                # Tạm dừng ngẫu nhiên từ 0.1 đến 1 giây để mô phỏng traffic thực tế
                time.sleep(random.uniform(0.1, 1.0))
                
        except KeyboardInterrupt:
            print("\n🛑 Đã dừng giả lập.")

if __name__ == "__main__":
    # Khởi tạo object với đường dẫn trỏ tới file log mà Alloy đang theo dõi
    simulator = PaymentGatewaySimulator("payment.log")
    simulator.run_simulation()