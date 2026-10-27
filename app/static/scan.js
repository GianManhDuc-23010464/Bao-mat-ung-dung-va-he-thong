// Quét QR ngay trên web: đọc khung hình camera bằng jsQR, thấy link điểm danh thì mở /checkin luôn.
(function () {
  const video = document.getElementById("scan-video");
  const canvas = document.getElementById("scan-canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const box = document.getElementById("scan-box");
  const statusEl = document.getElementById("scan-status");
  const startBtn = document.getElementById("scan-start");
  const stopBtn = document.getElementById("scan-stop");
  const photoLabel = document.getElementById("scan-photo-label");
  const photoInput = document.getElementById("scan-photo");
  let stream = null;
  let done = false;

  function setStatus(text) { statusEl.textContent = text; }

  // Chỉ nhận link /checkin có s và c; luôn mở trên chính máy chủ đang dùng (tránh chuyển hướng ra ngoài)
  function checkinPath(text) {
    let url;
    try { url = new URL(text, window.location.href); } catch (e) { return null; }
    if (url.pathname !== "/checkin") return null;
    const s = url.searchParams.get("s");
    const c = url.searchParams.get("c");
    if (!/^\d+$/.test(s || "") || !/^[0-9a-f]+$/.test(c || "")) return null;
    return "/checkin?" + new URLSearchParams({ s: s, c: c }).toString();
  }

  function handle(text) {
    const path = checkinPath(text);
    if (!path) { setStatus("Đây không phải mã điểm danh. Hãy quét mã trên máy chiếu."); return false; }
    done = true;
    stop();
    setStatus("Đang ghi nhận...");
    window.location.href = path;
    return true;
  }

  function decode(source, width, height) {
    if (!width || !height) return null;
    canvas.width = width;
    canvas.height = height;
    ctx.drawImage(source, 0, 0, width, height);
    const img = ctx.getImageData(0, 0, width, height);
    return jsQR(img.data, width, height, { inversionAttempts: "dontInvert" });
  }

  function tick() {
    if (!stream || done) return;
    if (video.readyState >= video.HAVE_ENOUGH_DATA) {
      const found = decode(video, video.videoWidth, video.videoHeight);
      if (found && found.data && handle(found.data)) return;
    }
    requestAnimationFrame(tick);
  }

  function stop() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
    box.classList.add("d-none");
    stopBtn.classList.add("d-none");
    startBtn.classList.remove("d-none");
  }

  function showPhotoFallback(message) {
    setStatus(message);
    photoLabel.classList.remove("d-none");
  }

  async function start() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.isSecureContext) {
      showPhotoFallback("Trình duyệt chỉ cho bật camera trực tiếp khi trang chạy HTTPS. " +
        "Hãy bấm \"Chụp ảnh mã QR\", hoặc dùng ứng dụng camera của điện thoại để quét.");
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } }, audio: false,
      });
    } catch (e) {
      showPhotoFallback("Không bật được camera (chưa cấp quyền?). Hãy bấm \"Chụp ảnh mã QR\".");
      return;
    }
    video.srcObject = stream;
    await video.play();
    box.classList.remove("d-none");
    startBtn.classList.add("d-none");
    stopBtn.classList.remove("d-none");
    setStatus("Hướng camera vào mã QR trên máy chiếu...");
    requestAnimationFrame(tick);
  }

  photoInput.addEventListener("change", function () {
    const file = photoInput.files && photoInput.files[0];
    if (!file) return;
    setStatus("Đang đọc ảnh...");
    const img = new Image();
    const src = URL.createObjectURL(file);
    img.onload = function () {
      // Thu nhỏ ảnh lớn cho nhanh, vẫn đủ nét để đọc QR
      const scale = Math.min(1, 1200 / Math.max(img.naturalWidth, img.naturalHeight));
      const found = decode(img, Math.round(img.naturalWidth * scale), Math.round(img.naturalHeight * scale));
      URL.revokeObjectURL(src);
      photoInput.value = "";
      if (!found || !found.data) { setStatus("Không đọc được mã trong ảnh, hãy chụp lại rõ hơn."); return; }
      handle(found.data);
    };
    img.onerror = function () { URL.revokeObjectURL(src); setStatus("Không mở được ảnh."); };
    img.src = src;
  });

  startBtn.addEventListener("click", start);
  stopBtn.addEventListener("click", function () { stop(); setStatus("Đã tắt camera."); });
  window.addEventListener("pagehide", stop);
})();
