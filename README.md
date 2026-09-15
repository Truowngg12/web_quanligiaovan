# Hệ thống Quản lý Vận đơn và Đối soát Tài chính Chặng cuối
**Last-Mile Waybill Management & Financial Reconciliation System**

> Đồ án tốt nghiệp — Trường Đại học Nguyễn Tất Thành (NTTU)

---

## ⚡ Khởi chạy nhanh (3 bước)

```bash
# 1. Cài thư viện
pip install -r requirements.txt

# 2. Tạo dữ liệu mẫu
python seed.py

# 3. Chạy ứng dụng
python app.py
```

Mở trình duyệt: **http://localhost:5000**

---

## 🔑 Tài khoản mặc định

| Vai trò | Đăng nhập bằng | Tài khoản | Mật khẩu |
|---------|---------------|-----------|----------|
| Admin | Email | `admin@vandon.com` | `admin123` |
| Tài xế 1 | Số điện thoại | `0911111111` | `driver123` |
| Tài xế 2 | Số điện thoại | `0922222222` | `driver123` |
| Tài xế 3 | Số điện thoại | `0933333333` | `driver123` |

> **Tip mobile:** Mở `http://<IP_máy>:5000` trên điện thoại cùng mạng WiFi để thử giao diện tài xế.

---

## 🗂️ Cấu trúc thư mục

```
vandon_app/
├── app.py              ← Flask app, toàn bộ routes & business logic
├── models.py           ← SQLAlchemy ORM (5 bảng)
├── seed.py             ← Tạo dữ liệu mẫu
├── requirements.txt
├── static/
│   ├── css/style.css   ← Custom CSS (sidebar, badges, mobile)
│   └── js/dashboard.js ← Chart.js + AJAX helpers
└── templates/
    ├── login.html
    ├── admin/
    │   ├── base.html           ← Sidebar layout
    │   ├── dashboard.html      ← Thống kê + biểu đồ
    │   ├── waybills.html       ← Bảng vận đơn + điều phối
    │   ├── waybill_create.html ← Tạo vận đơn
    │   ├── waybill_detail.html ← Chi tiết + lịch sử
    │   ├── drivers.html        ← Danh sách tài xế
    │   ├── driver_create.html  ← Thêm tài xế
    │   └── reconciliation.html ← Đối soát COD
    └── driver/
        ├── base.html   ← Mobile layout
        ├── tasks.html  ← Danh sách tác vụ
        └── update.html ← Cập nhật trạng thái giao
```

---

## 📊 Sơ đồ CSDL

```
ADMIN ──────────────────── VAN_DON ──────────────── TAI_XE
(MaAdmin, TenAdmin,        (MaVanDon PK,            (MaTaiXe, TenTaiXe,
 Email UNIQUE,              ThongTinNhan,             DienThoai UNIQUE,
 MatKhau bcrypt)            TienCOD, CuocPhi,         MatKhau bcrypt,
                            TrangThai,                KhuVuc,
                            MaAdmin FK,               SoDuVi)
                            MaTaiXe FK nullable)
                                │
               ┌────────────────┴───────────────┐
               ▼                                ▼
         LICH_SU_LOG                       GIAO_DICH
         (MaLog, MaVanDon FK,              (MaGiaoDich,
          TrangThaiCu,                      MaTaiXe FK,
          TrangThaiMoi,                     MaAdmin FK,
          GhiChu,                           SoTien,
          ThoiGian)                         SoTienThucThu,
                                            ThoiGian, GhiChu)
```

---

## 🔄 Quy trình nghiệp vụ

```
[Admin] Tạo vận đơn
    │  TrangThai = "Chờ điều phối"
    │  Ghi LICH_SU_LOG
    ▼
[Admin] Điều phối tài xế
    │  TrangThai = "Đang đi giao"
    │  Ghi LICH_SU_LOG
    ▼
[Tài xế — Mobile] Cập nhật kết quả
    ├─ Thành công → TrangThai = "Thành công"
    │               TAI_XE.SoDuVi += TienCOD  ← ATOMIC
    │               Ghi LICH_SU_LOG
    └─ Thất bại  → TrangThai = "Giao thất bại"
                    SoDuVi KHÔNG thay đổi
                    Ghi LICH_SU_LOG + lý do
    ▼
[Admin] Đối soát cuối ca
    │  Chọn tài xế → xem SoDuVi & danh sách đơn
    │  Nhập số tiền thực thu → Xác nhận
    │  TrangThai → "Đã đối soát"  ← ATOMIC
    │  TAI_XE.SoDuVi = 0.00
    └─ Ghi GIAO_DICH (audit log vĩnh viễn)
```

---

## 🛠️ Tech Stack

| Layer | Công nghệ |
|-------|-----------|
| Backend | Python 3.x + Flask 3.0 |
| ORM | Flask-SQLAlchemy |
| DB | SQLite (dev) / MySQL (prod) |
| Auth | bcrypt + Flask Session |
| Frontend | Bootstrap 5.3 + Bootstrap Icons |
| Chart | Chart.js 4.4 |
| AJAX | Fetch API (vanilla JS) |

---

## 🔐 Bảo mật

- Mật khẩu được hash bằng **Bcrypt** (cost factor 12)
- Session-based authentication với role check middleware
- Route guards: `@admin_required` / `@driver_required`
- Guard chống cập nhật trùng lặp trạng thái vận đơn
- Mọi thao tác tài chính chạy trong **atomic DB transaction**
- Có thể xuất báo cáo vận đơn dạng **Excel (.xlsx)** từ Dashboard hoặc danh sách vận đơn
- Nhập email người nhận để tự động gửi thông báo khi giao thành công hoặc thất bại

### Cấu hình gửi email

Mặc định email bị tắt để chạy an toàn ở môi trường phát triển. Để bật gửi email qua SMTP:

```bash
MAIL_ENABLED=true
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_gmail@gmail.com
MAIL_PASSWORD="mật khẩu ứng dụng Gmail"
MAIL_FROM="VanDon Express <your_gmail@gmail.com>"
```

Không đưa mật khẩu SMTP vào mã nguồn hoặc commit vào repository.

---

## 📱 Responsive

- **Desktop** (≥992px): Sidebar cố định, bảng dữ liệu đầy đủ
- **Tablet** (768–991px): Sidebar thu gọn bằng hamburger button
- **Mobile** (<768px): Giao diện Tài xế tối ưu cho thao tác một tay

---

*© 2024 — NTTU IT Department — Last-Mile Logistics System*
