# Điểm danh QR chống gian lận

Ứng dụng web điểm danh bằng mã QR đổi mỗi 5 giây. Dự án môn **Bảo mật ứng dụng và hệ thống**.

Giảng viên chiếu mã QR lên màn hình. Sinh viên đăng nhập sẵn trên điện thoại, quét mã là được ghi nhận ngay. Mã chỉ có hiệu lực trong 5 giây nên không thể chụp gửi cho người vắng mặt. Kết quả mỗi buổi được nối thành chuỗi băm và ký số, nên mọi chỉnh sửa trực tiếp trong cơ sở dữ liệu đều bị phát hiện.

## Mục lục

1. [Chức năng](#1-chức-năng)
2. [Cơ chế bảo mật](#2-cơ-chế-bảo-mật)
3. [Công nghệ và cấu trúc thư mục](#3-công-nghệ-và-cấu-trúc-thư-mục)
4. [Cài đặt](#4-cài-đặt)
5. [Tạo dữ liệu mẫu](#5-tạo-dữ-liệu-mẫu)
6. [Chạy ứng dụng](#6-chạy-ứng-dụng)
7. [Tài khoản thử](#7-tài-khoản-thử)
8. [Cách demo](#8-cách-demo)
9. [Xử lý sự cố](#9-xử-lý-sự-cố)
10. [Chạy test](#10-chạy-test)
11. [Giới hạn của hệ thống](#11-giới-hạn-của-hệ-thống)

## 1. Chức năng

**Giảng viên**
- Xem danh sách lớp mình dạy và 10 buổi của mỗi lớp.
- **Tạo buổi điểm danh**: màn hình chiếu hiện mã QR lớn, tự đổi mỗi 5 giây, kèm số sinh viên đã điểm danh / sĩ số và danh sách tên (mới nhất ở trên), cập nhật mỗi giây.
- **Xác nhận & kết thúc**: đóng buổi, mọi lượt quét sau đó bị từ chối.
- Xem kết quả buổi, sửa tay có mặt / vắng từng sinh viên, **Chốt buổi** để ký số kết quả.
- Bảng điểm danh của lớp (sinh viên × 10 buổi, tổng số buổi vắng), nút **Kiểm tra toàn vẹn** cho từng buổi đã chốt.

**Sinh viên**
- Đăng nhập sẵn trên điện thoại (giữ đăng nhập 30 ngày).
- Điểm danh bằng một trong hai cách:
  - Quét QR bằng ứng dụng camera của điện thoại, mở link là được ghi nhận ngay.
  - Bấm **Quét mã QR điểm danh** ngay trong web, đọc được mã là được ghi nhận ngay (cần chạy HTTPS, xem [mục 6](#6-chạy-ứng-dụng)).
- Trang **Tình trạng điểm danh của tôi**: mỗi môn một bảng (có mặt / vắng / chưa diễn ra), kèm tổng số buổi vắng.

## 2. Cơ chế bảo mật

| Thành phần | Cách làm |
|---|---|
| Mã QR động | `HMAC-SHA256(khóa bí mật của buổi, khung 5 giây)`, lấy 10 ký tự đầu. Chỉ chấp nhận mã của khung hiện tại, so sánh bằng `hmac.compare_digest`. Khóa không bao giờ gửi xuống trình duyệt và bị xóa khi chốt buổi. |
| Kiểm tra lượt quét | Theo thứ tự: đã đăng nhập → thuộc lớp → buổi đang mở → mã đúng khung hiện tại → chưa điểm danh. Giới hạn 10 lượt quét/phút mỗi tài khoản. |
| Chuỗi băm | Bảng sự kiện điểm danh chỉ thêm, không sửa, không xóa. Mỗi sự kiện chứa hash của sự kiện trước (SHA-256), mỗi buổi một chuỗi riêng. |
| Ký số | Khi chốt buổi, hash cuối được ký bằng Ed25519. Khóa riêng nằm trong `keys/`, ngoài CSDL. Sửa tay sau khi chốt thì nối thêm sự kiện và ký lại. |
| Kiểm tra toàn vẹn | Tính lại toàn bộ chuỗi và xác minh chữ ký, chỉ ra đúng sự kiện bị sửa hoặc bị xóa. |
| Web | Mật khẩu băm bcrypt; thông báo đăng nhập sai không lộ tài khoản có tồn tại hay không; CSRF token cho mọi form POST; phân quyền phía server cho mọi route; cookie `HttpOnly` + `SameSite=Lax` (thêm `Secure` khi chạy HTTPS); Content-Security-Policy; mã QR được che trong log. |

## 3. Công nghệ và cấu trúc thư mục

Python, Flask, Flask-Login, Flask-WTF, Flask-SQLAlchemy, SQLite, `bcrypt`, `cryptography` (Ed25519, chứng chỉ HTTPS), Bootstrap 5, `qrcode.js` (vẽ QR), `jsQR` (quét QR trong web), `pytest`.

```
app/
├── __init__.py      # create_app, đăng ký blueprint, lệnh `flask seed`
├── config.py        # cấu hình, đọc .env
├── models.py        # bảng CSDL
├── auth.py          # đăng nhập / đăng xuất, phân quyền
├── lecturer.py      # trang và API của giảng viên
├── student.py       # /checkin, /scan, /me
├── qr.py            # sinh và kiểm tra mã theo khung 5 giây
├── integrity.py     # chuỗi băm, ký số, kiểm tra toàn vẹn
├── security.py      # header bảo mật, che mã QR trong log
├── tls.py           # chứng chỉ HTTPS tự ký, server HTTPS
├── seed.py          # dữ liệu mẫu
├── templates/
└── static/
tests/               # pytest
run.py               # chạy server
```

Các thư mục sinh ra khi chạy (không đưa lên git): `instance/` (CSDL `app.db`), `keys/` (khóa ký số và chứng chỉ HTTPS), `.env`.

## 4. Cài đặt

Cần Python 3.10 trở lên. Mở Terminal (Windows: PowerShell) tại thư mục dự án.

**Tạo môi trường ảo và cài thư viện:**

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Tạo file `.env`** từ file mẫu (Windows dùng `copy` thay cho `cp`):
```bash
cp .env.example .env
```

Tạo một chuỗi ngẫu nhiên:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Mở `.env` và điền:

```
SECRET_KEY=<dán chuỗi vừa tạo>
BASE_URL=
HTTPS=1
```

| Biến | Ý nghĩa |
|---|---|
| `SECRET_KEY` | Khóa ký cookie phiên. Bắt buộc điền, nếu để trống mọi người bị đăng xuất mỗi lần khởi động lại. |
| `BASE_URL` | Địa chỉ dùng trong link QR. Để trống thì tự phát hiện IP mạng nội bộ của máy. Chỉ cần điền khi phát hiện sai (ví dụ máy có nhiều card mạng). |
| `HTTPS` | `1` = chạy HTTPS bằng chứng chỉ tự ký, cần để quét QR ngay trong web trên điện thoại. Để trống = HTTP. |

## 5. Tạo dữ liệu mẫu

```bash
flask --app app seed
```

Lệnh này **xóa CSDL cũ** (`instance/app.db`) và tạo lại từ đầu, dùng để reset trước mỗi lần demo:
- 1 giảng viên, 20 sinh viên, 3 học phần, mỗi lớp 10 sinh viên.
- Mỗi học phần 10 buổi: buổi 1–4 đã chốt (có chữ ký), buổi 5–10 chưa diễn ra. Giảng viên có thể mở bất kỳ buổi nào chưa diễn ra.

Lần chạy đầu tiên tự sinh cặp khóa Ed25519 vào `keys/`. Đừng xóa thư mục này khi đã có dữ liệu, nếu không các chữ ký cũ sẽ không xác minh được (khi đó chạy lại `seed`).

## 6. Chạy ứng dụng

```bash
python run.py
```

Khi khởi động, Terminal in ra hai địa chỉ, ví dụ:

```
 * Running on https://127.0.0.1:5000
 * Running on https://192.168.0.105:5000
```

**Laptop và điện thoại đều mở địa chỉ có IP mạng nội bộ** (`https://192.168.x.x:5000`). Địa chỉ `127.0.0.1` chỉ trỏ về chính thiết bị đang dùng, nên điện thoại không vào được bằng địa chỉ này. Mã QR trên máy chiếu cũng luôn dùng địa chỉ IP mạng nội bộ.

Dừng server: bấm `Ctrl + C`.

**Về HTTPS (`HTTPS=1`):**
- Trình duyệt điện thoại chỉ cho bật camera trên trang web khi trang chạy HTTPS. Vì vậy chức năng **Quét mã QR điểm danh** trong web cần HTTPS. Cách quét bằng ứng dụng camera của điện thoại thì chạy được với cả HTTP.
- Lần đầu chạy, ứng dụng tự sinh chứng chỉ tự ký vào `keys/tls_cert.pem` và `keys/tls_key.pem`. Khi đổi mạng (IP khác), chứng chỉ được sinh lại.
- Vì chứng chỉ tự ký, mỗi máy sẽ hiện cảnh báo bảo mật **một lần**:
  - Chrome: **Nâng cao** → **Tiếp tục truy cập 192.168.x.x (không an toàn)**.
  - Safari (macOS, iPhone): **Hiển thị chi tiết** → **truy cập trang web này** → **Truy cập trang web**.
- Sau khi bật hoặc tắt HTTPS, mọi người cần đăng nhập lại (cookie đổi cờ `Secure`).

## 7. Tài khoản thử

| Vai trò | Tên đăng nhập | Mật khẩu |
|---|---|---|
| Giảng viên | `gv01` (Nguyễn Văn An) | `Matkhau@123` |
| Sinh viên | `sv01` … `sv20` | `Matkhau@123` |

| Học phần | Mã | Sinh viên |
|---|---|---|
| Bảo mật ứng dụng và hệ thống | `BMUD01` | sv01–sv10 |
| Mạng máy tính | `MMT01` | sv06–sv15 |
| Cơ sở dữ liệu | `CSDL01` | sv01–sv05, sv16–sv20 |

## 8. Cách demo

1. **Laptop**: mở `https://<IP-laptop>:5000`, đăng nhập `gv01` → chọn lớp `BMUD01` → bấm **Tạo buổi điểm danh** ở buổi 5. Màn hình chiếu QR hiện ra (nên bật toàn màn hình).
2. **Điện thoại**: kết nối **cùng Wi-Fi** với laptop, mở cùng địa chỉ, đăng nhập `sv01`.
3. **Quét QR**, chọn một trong hai cách:
   - Trong web: bấm **Quét mã QR điểm danh** → **Bật camera để quét** → cho phép dùng camera → hướng vào mã QR.
   - Bằng ứng dụng Camera của điện thoại: quét mã rồi bấm vào link hiện ra.

   Trang hiện **"Điểm danh thành công lúc HH:MM:SS"**. Trên máy chiếu, số lượng và danh sách cập nhật trong khoảng 1 giây.
4. **Các trường hợp bị từ chối**:
   - Quét lại lần nữa → "Bạn đã điểm danh buổi này lúc ...".
   - Chụp ảnh QR, mở link sau hơn 5 giây → "Mã đã đổi".
   - Đăng nhập sinh viên lớp khác (ví dụ `sv11`) → "Bạn không thuộc lớp này".
5. Bấm **Xác nhận & kết thúc** → sửa tay nếu cần → **Chốt buổi** → **Kiểm tra toàn vẹn** → "Còn nguyên vẹn".
6. **Phát hiện sửa dữ liệu**: mở `instance/app.db` bằng DB Browser for SQLite (hoặc `sqlite3`). Sửa cột `kind` của một dòng trong bảng `attendance_events`, hoặc xóa một dòng, rồi bấm lại **Kiểm tra toàn vẹn**. Hệ thống báo đỏ, chỉ ra đúng sự kiện bị sửa.

## 9. Xử lý sự cố

**Không mở được trang trên điện thoại**
- Kiểm tra đang mở địa chỉ `192.168.x.x`, **không phải** `127.0.0.1`.
- Mở đúng giao thức: chạy với `HTTPS=1` thì dùng `https://`, không thì dùng `http://`. Sai giao thức thì Safari báo "không thể thiết lập kết nối bảo mật".
- Điện thoại và laptop phải cùng một mạng Wi-Fi.
- Tường lửa:
  - macOS: nếu được hỏi "Cho phép Python nhận kết nối đến?", chọn **Cho phép**.
  - Windows: cho phép Python qua Windows Defender Firewall, chọn cả mạng Private.
- **Wi-Fi của trường có thể chặn kết nối giữa các thiết bị.** Khi đó bật hotspot trên điện thoại, cho laptop kết nối vào hotspot, chạy lại `python run.py` và dùng IP mới in ra.

**Cổng 5000 đã bị dùng (`Address already in use`)**
- macOS: tắt **AirPlay Receiver** trong System Settings → General → AirDrop & Handoff.
- Hoặc tắt chương trình khác đang dùng cổng 5000 (kể cả một cửa sổ `python run.py` cũ).

**Không bật được camera, trang chỉ hiện nút "Chụp ảnh mã QR"**
- Trang đang chạy HTTP. Đặt `HTTPS=1` trong `.env`, chạy lại và mở bằng `https://`.
- Hoặc trình duyệt chưa được cấp quyền camera:
  - iPhone: Cài đặt → Safari → Camera.
  - Android: biểu tượng bên trái thanh địa chỉ → Quyền → Camera.

**Các thông báo khi quét**
- **"Mã đã đổi"**: mã chỉ sống trong khung 5 giây hiện tại, hãy quét lại. Đồng hồ lấy từ máy chủ nên giờ trên điện thoại không ảnh hưởng.
- **Đăng nhập xong không tự điểm danh**: đúng thiết kế, vì mã cũ đã hết hạn. Hãy quét lại mã mới.
- **"Bạn thao tác quá nhanh"**: mỗi tài khoản tối đa 10 lượt quét/phút, chờ một chút rồi thử lại.

**QR không hiện trên máy chiếu**
- Laptop cần Internet để tải Bootstrap, `qrcode.js` và `jsQR` từ CDN.

**Lỗi `Invalid requirement: '#'` khi chạy `pip`**
- Terminal trên macOS (zsh) không hiểu phần chú thích `# ...` dán cùng dòng lệnh. Chỉ dán phần lệnh.

## 10. Chạy test

```bash
pytest
```

51 test bao phủ: chỉ chấp nhận mã của khung hiện tại; từ chối mã cũ, mã sai, buổi đã kết thúc, sinh viên không thuộc lớp; quét 2 lần chỉ ghi 1 sự kiện; phân quyền giữa các giảng viên; phát hiện dòng bị sửa hoặc bị xóa; ký lại khi sửa tay sau khi chốt; từ chối form thiếu CSRF token; trang quét QR; chứng chỉ HTTPS.

## 11. Giới hạn của hệ thống

- Một người gọi video cho bạn đang ở nhà, bạn đó quét QR qua màn hình kịp trong 5 giây vẫn điểm danh được.
- Người biết mật khẩu của bạn khác có thể đăng nhập tài khoản đó trên điện thoại mình và quét hộ.
- Hệ thống không kiểm tra vị trí, Wi-Fi hay thiết bị. Chống gian lận chủ yếu nhờ mã sống ngắn, chỉ quét được khi đang ở trước máy chiếu.
- Chữ ký số bảo vệ dữ liệu khỏi bị sửa trực tiếp trong CSDL. Nhưng nếu kẻ tấn công lấy được cả khóa riêng trong `keys/` thì có thể ký lại, vì vậy cần bảo vệ thư mục này.
- Chứng chỉ HTTPS là tự ký, chỉ phù hợp để demo trong mạng nội bộ. Server dùng là server phát triển của Flask, không dùng cho môi trường thật.
