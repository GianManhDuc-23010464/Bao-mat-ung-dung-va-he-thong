# Điểm danh QR chống gian lận

Ứng dụng web điểm danh bằng mã QR đổi mỗi 5 giây. Dự án môn Bảo mật ứng dụng và hệ thống.

## 1. Giới thiệu và chức năng

**Giảng viên**
- Xem danh sách lớp mình dạy, danh sách 10 buổi của mỗi lớp.
- Mở buổi điểm danh: màn hình chiếu hiện mã QR lớn, tự đổi mỗi 5 giây, kèm số sinh viên đã điểm danh / sĩ số và danh sách tên (mới nhất ở trên).
- "Xác nhận & kết thúc": đóng buổi, mọi lượt quét sau đó bị từ chối.
- Xem kết quả buổi, sửa tay có mặt / vắng từng sinh viên, "Chốt buổi" để ký số kết quả.
- Bảng điểm danh của lớp (sinh viên × 10 buổi, tổng số buổi vắng), nút "Kiểm tra toàn vẹn" cho từng buổi đã chốt.

**Sinh viên**
- Đăng nhập sẵn trên điện thoại (giữ đăng nhập 30 ngày).
- Quét QR bằng camera, link mở ra là được ghi nhận ngay.
- Trang "Tình trạng điểm danh của tôi": mỗi môn một bảng, kèm tổng số buổi vắng.

**Cơ chế bảo mật chính**
- Mã QR = HMAC-SHA256(khóa bí mật của buổi, khung thời gian 5 giây), chỉ chấp nhận mã của khung hiện tại. Khóa không bao giờ gửi xuống trình duyệt và bị xóa khi chốt buổi.
- Bảng sự kiện điểm danh chỉ thêm, không sửa, không xóa; mỗi buổi có một chuỗi băm SHA-256 riêng.
- Khi chốt buổi, hash cuối của chuỗi được ký bằng Ed25519 (khóa lưu ở thư mục `keys/`, ngoài CSDL). Sửa tay sau khi chốt sẽ nối thêm sự kiện và ký lại.
- "Kiểm tra toàn vẹn" tính lại toàn bộ chuỗi và xác minh chữ ký, chỉ ra đúng sự kiện bị sửa hoặc xóa.
- Mật khẩu băm bcrypt, CSRF token cho mọi form POST, phân quyền phía server, cookie `HttpOnly` + `SameSite=Lax`, Content-Security-Policy, giới hạn 10 lượt quét/phút mỗi tài khoản, mã QR được che trong log.

## 2. Cài đặt

Cần Python 3.11 trở lên.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` thành `.env` rồi điền `SECRET_KEY` (một chuỗi ngẫu nhiên dài):

```bash
cp .env.example .env          # Windows: copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # dán kết quả vào SECRET_KEY=
```

`BASE_URL` để trống thì ứng dụng tự phát hiện IP mạng nội bộ của máy (ví dụ `http://192.168.1.5:5000`). Chỉ cần điền khi tự phát hiện sai, ví dụ máy có nhiều card mạng.

`HTTPS=1` để chạy HTTPS (xem mục 4). Để trống = HTTP.

## 3. Tạo dữ liệu mẫu

```bash
flask --app app seed
```

Lệnh này xóa CSDL cũ (`instance/app.db`) và tạo lại từ đầu. Dùng để reset trước mỗi lần demo. Dữ liệu mẫu: 1 giảng viên, 20 sinh viên, 3 học phần (mỗi lớp 10 sinh viên). Mỗi học phần 10 buổi: buổi 1–4 đã chốt, có chữ ký; buổi 5–10 chưa diễn ra. Giảng viên có thể mở bất kỳ buổi nào chưa diễn ra.

Lần chạy đầu tiên sẽ tự sinh cặp khóa Ed25519 vào `keys/`. Không xóa thư mục này sau khi đã có dữ liệu, nếu không các chữ ký cũ sẽ không xác minh được (khi đó chạy lại `seed`).

## 4. Chạy

```bash
python run.py
```

Máy chủ lắng nghe ở `0.0.0.0:5000`. Trên laptop mở `http://<IP-laptop>:5000` (IP in ra ở dòng `Running on http://...` khi khởi động).

**Chạy HTTPS (để sinh viên quét QR ngay trong web):** trình duyệt điện thoại chỉ cho bật camera trên trang web khi trang chạy HTTPS. Đặt `HTTPS=1` trong `.env` rồi chạy lại `python run.py`:

- Lần đầu ứng dụng tự sinh chứng chỉ tự ký vào `keys/tls_cert.pem` và `keys/tls_key.pem`, cấp cho IP mạng nội bộ hiện tại. Khi đổi mạng (IP khác) chứng chỉ được sinh lại.
- Mở `https://<IP-laptop>:5000`. Vì chứng chỉ tự ký, mỗi máy (laptop, từng điện thoại) sẽ hiện cảnh báo bảo mật **một lần**: chọn "Nâng cao" → "Tiếp tục truy cập" (Safari: "Hiển thị chi tiết" → "truy cập trang web này").
- Mã QR trên máy chiếu tự dùng link `https://...`. Cookie phiên có thêm cờ `Secure`, nên sau khi bật hoặc tắt HTTPS mọi người cần đăng nhập lại.

## 5. Tài khoản thử

| Vai trò | Tên đăng nhập | Mật khẩu |
|---|---|---|
| Giảng viên | `gv01` | `Matkhau@123` |
| Sinh viên | `sv01` … `sv20` | `Matkhau@123` |

Lớp: `BMUD01` có sv01–sv10, `MMT01` có sv06–sv15, `CSDL01` có sv01–sv05 và sv16–sv20.

## 6. Cách demo

1. Laptop: đăng nhập `gv01` → chọn lớp → bấm **"Tạo buổi điểm danh"** ở buổi 5 → màn hình chiếu QR (nên mở toàn màn hình, F11).
2. Điện thoại kết nối **cùng Wi-Fi** với laptop, mở `http://<IP-laptop>:5000`, đăng nhập một sinh viên của lớp (ví dụ `sv01` cho BMUD01).
3. Dùng camera điện thoại quét QR → trang hiện "Điểm danh thành công lúc ...". Cách khác: trên trang "Tình trạng điểm danh của tôi" bấm **"Quét mã QR điểm danh"** → **"Bật camera để quét"** để quét ngay trong web, đọc được mã là ghi nhận luôn. Camera trực tiếp cần chạy HTTPS (mục 4); với HTTP, trang chỉ cho chụp ảnh mã QR, dễ bị quá 5 giây. Trên máy chiếu, số lượng và danh sách cập nhật trong khoảng 1 giây.
4. Thử các trường hợp bị từ chối: quét lại lần nữa, chụp ảnh QR rồi mở link sau hơn 5 giây, đăng nhập sinh viên lớp khác (ví dụ `sv11` cho BMUD01).
5. Bấm **"Xác nhận & kết thúc"** → sửa tay nếu cần → **"Chốt buổi"** → **"Kiểm tra toàn vẹn"** → "Còn nguyên vẹn".
6. Demo phát hiện sửa dữ liệu: mở `instance/app.db` bằng DB Browser for SQLite (hoặc `sqlite3`), sửa cột `kind` của một dòng trong `attendance_events`, hoặc xóa một dòng, rồi bấm lại "Kiểm tra toàn vẹn". Hệ thống báo dòng đỏ chỉ đúng sự kiện bị sửa.

## 7. Xử lý sự cố

- **Điện thoại không mở được link trong QR:**
  - Kiểm tra điện thoại và laptop dùng **cùng một mạng Wi-Fi**.
  - Windows: khi chạy lần đầu, cho phép Python qua **tường lửa Windows** (chọn cả mạng Private). Nếu đã lỡ chặn: Windows Defender Firewall → Allow an app → bật Python.
  - Kiểm tra **cổng 5000** không bị chương trình khác chiếm, và trên điện thoại mở thử `http://<IP-laptop>:5000/login`.
  - Kiểm tra link trong QR có đúng IP của laptop không; nếu sai, đặt `BASE_URL=http://<IP-đúng>:5000` trong `.env`.
  - **Wi-Fi của trường có thể chặn kết nối giữa các thiết bị** (client isolation). Khi đó bật **hotspot trên điện thoại**, cho laptop kết nối vào hotspot đó, rồi chạy lại `python run.py`.
- **Quét xong báo "Mã đã đổi"**: mã chỉ sống trong khung 5 giây hiện tại, hãy quét lại mã đang hiện trên máy chiếu. Đồng hồ được lấy từ máy chủ nên giờ điện thoại không ảnh hưởng.
- **Sau khi đăng nhập không tự điểm danh**: đúng thiết kế, vì mã cũ đã hết hạn. Hãy quét lại mã mới.
- **Báo "Bạn thao tác quá nhanh"**: mỗi tài khoản tối đa 10 lượt quét/phút, chờ một chút rồi quét lại.
- **QR không hiện**: máy chiếu cần Internet để tải Bootstrap và `qrcode.js` từ CDN.
- **Nút "Bật camera để quét" chỉ hiện "Chụp ảnh mã QR"**: trang đang chạy HTTP hoặc chưa cấp quyền camera. Bật `HTTPS=1` (mục 4), mở bằng `https://`, rồi cho phép trình duyệt dùng camera.
- **macOS báo cổng 5000 đã bị dùng**: tắt "AirPlay Receiver" trong System Settings → General → AirDrop & Handoff.

## 8. Chạy test

```bash
pytest
```

## 9. Giới hạn của hệ thống

- Một người gọi video cho bạn đang ở nhà, bạn đó quét QR qua màn hình kịp trong 5 giây vẫn điểm danh được.
- Người biết mật khẩu của bạn khác có thể đăng nhập tài khoản đó trên điện thoại mình và quét hộ.
- Hệ thống không kiểm tra vị trí, Wi-Fi hay thiết bị; chống gian lận chủ yếu nhờ mã sống ngắn và chỉ quét được khi đang ở trước máy chiếu.
- Chữ ký số bảo vệ dữ liệu khỏi bị sửa trực tiếp trong CSDL, nhưng nếu kẻ tấn công lấy được cả khóa riêng trong `keys/` thì có thể ký lại. Vì vậy cần bảo vệ thư mục này.
