import json
import time
import random
from datetime import datetime, timezone
from pathlib import Path

class PaymentGatewaySimulator:
    def __init__(self, log_file_path):
        self.log_file = Path(log_file_path)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.providers = ["Momo", "ZaloPay", "VNPay", "ShopeePay"]
        self.endpoints = ["/api/checkout", "/api/apply_voucher", "/v1/create_order"]
        
    def _write_to_file(self, log_data):
        log_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_data) + "\n")
            

    def generate_business_log(self):
        events = [
            {"level": "INFO", "event": "payment_init", "order_id": f"ORD-{random.randint(1000, 9999)}", "amount": random.randint(30, 200) * 1000, "method": random.choice(self.providers)},
            {"level": "INFO", "event": "voucher_apply", "code": "FREESHIP50", "status": "success", "discount": 15000},
            {"level": "INFO", "event": "payment_success", "order_id": f"ORD-{random.randint(1000, 9999)}", "processing_time_ms": random.randint(200, 800)}
        ]
        self._write_to_file(random.choice(events))

    def generate_gateway_log(self):
        events = [
            {"level": "ERROR", "event": "gateway_timeout", "provider": random.choice(self.providers), "endpoint": random.choice(self.endpoints), "latency_ms": random.randint(5000, 8000)},
            {"level": "WARN", "event": "gateway_rejected", "provider": random.choice(self.providers), "reason": "insufficient_balance"}
        ]
        self._write_to_file(random.choice(events))

    def generate_security_log(self):
        fake_ip = f"{random.randint(100, 200)}.{random.randint(10, 99)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
        events = [
            {"level": "WARN", "event": "rate_limit_exceeded", "ip": fake_ip, "requests_per_sec": random.randint(20, 50)},
            {"level": "CRITICAL", "event": "brute_force_detected", "user_id": f"U-{random.randint(100, 999)}", "reason": "multiple_failed_otp"}
        ]
        self._write_to_file(random.choice(events))

    def generate_system_log(self):
        events = [
            {"level": "ERROR", "event": "db_connection_pool", "status": "exhausted", "active_connections": random.randint(200, 250)},
            {"level": "FATAL", "event": "app_crash", "exception": "NullPointerException"}
        ]
        self._write_to_file(random.choice(events))

    def run_simulation(self):
        print("Starting simulation...\n")
        try:
            while True:
                choice = random.choices(
                    [self.generate_business_log, self.generate_gateway_log, self.generate_security_log, self.generate_system_log],
                    weights=[60, 20, 10, 10],
                    k=1
                )[0]
                
                choice()

                time.sleep(random.uniform(0.1, 1.0))
                
        except KeyboardInterrupt:
            print("\nStop simulation.")

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    simulator = PaymentGatewaySimulator(project_root / "logs" / "payment.log")
    simulator.run_simulation()