const seatButtons = document.querySelectorAll(".seat:not(.booked):not(.held)");
const selectedSeatsElement = document.querySelector("[data-selected-seats]");
const totalElement = document.querySelector("[data-total]");
const holdButton = document.querySelector("[data-hold]");
const confirmButton = document.querySelector("[data-confirm]");
const addonInputs = document.querySelectorAll("[data-addon-price]");
const seatMap = document.querySelector("[data-showtime-id]");
const alertBox = document.querySelector("[data-booking-alert]");
let activeHoldId = "";
let activeIdempotencyKey = "";

function money(value) {
  return `${value.toLocaleString("vi-VN")}đ`;
}

function selectedSeats() {
  return [...document.querySelectorAll(".seat.selected")];
}

function selectedAddons() {
  return [...addonInputs].filter((input) => input.checked).map((input) => input.value);
}

function showAlert(message, type = "info") {
  if (!alertBox) {
    return;
  }
  alertBox.textContent = message;
  alertBox.dataset.type = type;
}

function updateSummary() {
  if (!selectedSeatsElement || !totalElement) {
    return;
  }

  const seats = selectedSeats();
  const seatTotal = seats.reduce((sum, seat) => sum + Number(seat.dataset.price), 0);
  const addonTotal = [...addonInputs]
    .filter((input) => input.checked)
    .reduce((sum, input) => sum + Number(input.dataset.addonPrice), 0);

  selectedSeatsElement.textContent = seats.length
    ? `Ghế: ${seats.map((seat) => seat.dataset.seat).join(", ")}`
    : "Chưa chọn ghế";
  totalElement.textContent = money(seatTotal + addonTotal);

  if (holdButton) {
    holdButton.disabled = seats.length === 0;
  }
  if (confirmButton) {
    confirmButton.disabled = !activeHoldId;
  }
}

seatButtons.forEach((button) => {
  button.addEventListener("click", () => {
    button.classList.toggle("selected");
    activeHoldId = "";
    activeIdempotencyKey = "";
    updateSummary();
  });
});

addonInputs.forEach((input) => {
  input.addEventListener("change", updateSummary);
});

if (holdButton && seatMap) {
  holdButton.addEventListener("click", async () => {
    const body = new URLSearchParams();
    body.set("seat_ids", selectedSeats().map((seat) => seat.dataset.seat).join(","));
    body.set("addons", selectedAddons().join(","));
    const response = await fetch(`/api/showtimes/${seatMap.dataset.showtimeId}/holds`, {
      method: "POST",
      body,
    });
    const data = await response.json();
    if (response.ok) {
      activeHoldId = data.hold_id;
      activeIdempotencyKey = `idem_${Date.now()}`;
      selectedSeats().forEach((seat) => {
        seat.classList.remove("selected");
        seat.classList.add("held_by_you");
      });
      showAlert(`Đã tạm giữ ghế đến ${data.expires_at}. Bấm xác nhận để hoàn tất đặt vé.`, "success");
    } else {
      showAlert(data.message || "Không thể tạm giữ ghế. Vui lòng chọn ghế khác.", "error");
    }
    updateSummary();
  });
}

if (confirmButton) {
  confirmButton.addEventListener("click", async () => {
    const body = new URLSearchParams();
    body.set("hold_id", activeHoldId);
    body.set("addons", selectedAddons().join(","));
    body.set("idempotency_key", activeIdempotencyKey);
    const response = await fetch("/bookings/confirm", {
      method: "POST",
      body,
    });
    const data = await response.json();
    if (response.ok) {
      showAlert("Đặt vé thành công. Đang mở vé của bạn...", "success");
      window.location.href = `/bookings/${data.booking_id}`;
    } else {
      showAlert(data.message || "Đặt vé thất bại. Vui lòng thử lại.", "error");
    }
  });
}
