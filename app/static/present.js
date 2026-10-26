(function () {
  const box = document.getElementById("qr");
  const qrUrl = box.dataset.qrUrl;
  const liveUrl = box.dataset.liveUrl;
  const doneUrl = box.dataset.doneUrl;
  const statusEl = document.getElementById("qr-status");
  const size = Math.floor(Math.min(window.innerWidth * 0.6, window.innerHeight * 0.72, 720));
  const code = new QRCode(box, { width: size, height: size, correctLevel: QRCode.CorrectLevel.M });
  let lastFrame = null;

  async function pollQr() {
    try {
      const r = await fetch(qrUrl, { cache: "no-store", credentials: "same-origin" });
      if (r.status === 409) { window.location = doneUrl; return; }
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      if (data.frame !== lastFrame) {
        code.clear();
        code.makeCode(data.url);
        lastFrame = data.frame;
      }
      statusEl.textContent = "Mã tự đổi mỗi 5 giây";
    } catch (e) {
      statusEl.textContent = "Mất kết nối tới máy chủ, đang thử lại...";
    }
  }

  async function pollLive() {
    try {
      const r = await fetch(liveUrl, { cache: "no-store", credentials: "same-origin" });
      if (!r.ok) return;
      const data = await r.json();
      document.getElementById("count").textContent = data.count;
      document.getElementById("total").textContent = data.total;
      const list = document.getElementById("present-list");
      list.replaceChildren(...data.students.map(function (s) {
        const li = document.createElement("li");
        li.className = "list-group-item d-flex justify-content-between";
        const name = document.createElement("span");
        name.textContent = s.name + " (" + s.student_code + ")";
        const t = document.createElement("span");
        t.className = "text-muted";
        t.textContent = s.time;
        li.append(name, t);
        return li;
      }));
    } catch (e) { /* thử lại ở lần sau */ }
  }

  pollQr(); pollLive();
  setInterval(pollQr, 1000);
  setInterval(pollLive, 1000);
})();
