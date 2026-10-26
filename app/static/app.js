// Hộp xác nhận cho các form có data-confirm (thay cho onsubmit inline để hợp CSP)
document.addEventListener("submit", function (e) {
  const msg = e.target.getAttribute("data-confirm");
  if (msg && !window.confirm(msg)) e.preventDefault();
});
