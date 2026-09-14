"""
seed.py — Tạo dữ liệu mẫu cho VanDon System
Chạy: python seed.py
Lưu ý: sẽ XOÁ và tạo lại toàn bộ CSDL.
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(__file__))

import bcrypt
from datetime import datetime, timedelta
from decimal import Decimal

from app import app, generate_waybill_id
from models import db, Admin, TaiXe, VanDon, LichSuLog, GiaoDich

# ── Dữ liệu mẫu ────────────────────────────────────────────
RECIPIENTS = [
    ("Nguyễn Thị Lan",    "0901110001", "123 Lê Lợi, P.Bến Nghé, Q.1, TP.HCM"),
    ("Trần Văn Minh",     "0901110002", "456 Nguyễn Huệ, P.Bến Nghé, Q.1, TP.HCM"),
    ("Lê Thị Hoa",        "0901110003", "789 Đồng Khởi, P.Bến Nghé, Q.1, TP.HCM"),
    ("Phạm Quốc Bảo",     "0901110004", "321 CMT8, P.11, Q.10, TP.HCM"),
    ("Võ Thị Kim Oanh",   "0901110005", "654 Phan Xích Long, P.7, Bình Thạnh, TP.HCM"),
    ("Đặng Hữu Phúc",     "0901110006", "111 Lý Thường Kiệt, P.7, Q.10, TP.HCM"),
    ("Ngô Thị Thanh Xuân","0901110007", "222 Trần Hưng Đạo, P.Cô Giang, Q.1, TP.HCM"),
    ("Đinh Văn Long",     "0901110008", "333 Bà Triệu, P.4, Tân Bình, TP.HCM"),
    ("Bùi Thị Thu Hà",   "0901110009", "444 Nam Kỳ Khởi Nghĩa, P.8, Q.3, TP.HCM"),
    ("Hoàng Minh Đức",   "0901110010", "555 Đinh Tiên Hoàng, P.3, Bình Thạnh, TP.HCM"),
    ("Phan Thị Yến Nhi",  "0901110011", "666 Hoàng Diệu, P.12, Q.4, TP.HCM"),
    ("Lý Văn Cảnh",      "0901110012", "777 Trường Chinh, P.13, Tân Bình, TP.HCM"),
    ("Mai Thị Nga",      "0901110013", "888 Xô Viết Nghệ Tĩnh, P.26, Bình Thạnh, TP.HCM"),
    ("Vũ Hồng Quân",     "0901110014", "999 Phan Đình Phùng, P.17, Phú Nhuận, TP.HCM"),
    ("Chu Thị Diễm My",  "0901110015", "101 Cách Mạng Tháng 8, P.5, Q.3, TP.HCM"),
]

COD_OPTIONS = [0, 50_000, 100_000, 150_000, 200_000, 250_000, 300_000, 500_000, 750_000]

FAILURE_REASONS = [
    "Khách không có mặt tại địa chỉ giao hàng.",
    "Số điện thoại không liên lạc được.",
    "Địa chỉ không tồn tại hoặc không tìm thấy.",
    "Khách từ chối nhận hàng.",
    "Khu vực ngập lụt, không thể tiếp cận.",
]

STATUS_SEQUENCE = [
    VanDon.STATUS_PENDING,      # 1
    VanDon.STATUS_PENDING,      # 2
    VanDon.STATUS_DELIVERING,   # 3
    VanDon.STATUS_DELIVERING,   # 4
    VanDon.STATUS_DELIVERING,   # 5
    VanDon.STATUS_SUCCESS,      # 6
    VanDon.STATUS_SUCCESS,      # 7
    VanDon.STATUS_SUCCESS,      # 8
    VanDon.STATUS_SUCCESS,      # 9
    VanDon.STATUS_FAILED,       # 10
    VanDon.STATUS_FAILED,       # 11
    VanDon.STATUS_RECONCILED,   # 12
    VanDon.STATUS_RECONCILED,   # 13
    VanDon.STATUS_RECONCILED,   # 14
    VanDon.STATUS_SUCCESS,      # 15 — pending reconciliation
]


def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("[SEED] Database reset.")

        # ── Admin ───────────────────────────────────────────
        admin_pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        admin = Admin(TenAdmin="Nguyễn Quản Trị", Email="admin@vandon.com", MatKhau=admin_pw)
        db.session.add(admin)
        db.session.flush()
        print(f"  ✔ Admin: admin@vandon.com / admin123")

        # ── Tài xế ─────────────────────────────────────────
        drv_pw = bcrypt.hashpw(b"driver123", bcrypt.gensalt()).decode()
        drivers_raw = [
            ("Nguyễn Văn An",  "0911111111", "Quận 1 – Quận 3"),
            ("Trần Thị Bình",  "0922222222", "Quận 7 – Quận 4"),
            ("Lê Văn Cường",   "0933333333", "Bình Thạnh – Phú Nhuận"),
        ]
        drivers = []
        for ten, sdt, kv in drivers_raw:
            d = TaiXe(TenTaiXe=ten, DienThoai=sdt, MatKhau=drv_pw, KhuVuc=kv)
            db.session.add(d)
            drivers.append(d)
        db.session.flush()
        for d in drivers:
            print(f"  ✔ Tài xế: {d.DienThoai} / driver123 — {d.TenTaiXe}")

        # ── Vận đơn ─────────────────────────────────────────
        for idx, (ten, sdt, dc) in enumerate(RECIPIENTS):
            target_status = STATUS_SEQUENCE[idx]
            cod   = Decimal(str(random.choice(COD_OPTIONS)))
            fee   = Decimal("20000") + cod * Decimal("0.01")
            info  = f"{ten} | {sdt} | {dc}"
            ma_vd = generate_waybill_id()

            # Assign driver only for non-pending
            driver = random.choice(drivers) if target_status != VanDon.STATUS_PENDING else None

            vd = VanDon(
                MaVanDon     = ma_vd,
                ThongTinNhan = info,
                TienCOD      = cod,
                CuocPhi      = fee,
                TrangThai    = target_status,
                MaAdmin      = admin.MaAdmin,
                MaTaiXe      = driver.MaTaiXe if driver else None,
                NgayTao      = datetime.utcnow() - timedelta(hours=random.randint(1, 36)),
            )
            db.session.add(vd)
            db.session.flush()

            def add_log(cu, moi, ghi_chu=""):
                db.session.add(LichSuLog(
                    MaVanDon=ma_vd, TrangThaiCu=cu,
                    TrangThaiMoi=moi, GhiChu=ghi_chu,
                ))

            # Initial log — always
            add_log(None, VanDon.STATUS_PENDING,
                    f"Tạo vận đơn mới bởi {admin.TenAdmin}")

            if target_status in [VanDon.STATUS_DELIVERING, VanDon.STATUS_SUCCESS,
                                  VanDon.STATUS_FAILED,     VanDon.STATUS_RECONCILED]:
                add_log(VanDon.STATUS_PENDING, VanDon.STATUS_DELIVERING,
                        f"Điều phối cho tài xế: {driver.TenTaiXe}")

            if target_status in [VanDon.STATUS_SUCCESS, VanDon.STATUS_RECONCILED]:
                add_log(VanDon.STATUS_DELIVERING, VanDon.STATUS_SUCCESS,
                        "Tài xế xác nhận giao hàng thành công.")
                # Cộng COD vào ví tài xế
                driver.SoDuVi = driver.SoDuVi + cod

            if target_status == VanDon.STATUS_FAILED:
                reason = random.choice(FAILURE_REASONS)
                add_log(VanDon.STATUS_DELIVERING, VanDon.STATUS_FAILED,
                        f"Lý do: {reason}")

            if target_status == VanDon.STATUS_RECONCILED:
                add_log(VanDon.STATUS_SUCCESS, VanDon.STATUS_RECONCILED,
                        f"Đối soát bởi {admin.TenAdmin}")

        db.session.flush()

        # ── Tạo một giao dịch đối soát mẫu ─────────────────
        # Dùng driver đầu tiên có reconciled waybills
        sample_driver = drivers[2]  # Lê Văn Cường
        settled_vd = VanDon.query.filter_by(
            MaTaiXe=sample_driver.MaTaiXe,
            TrangThai=VanDon.STATUS_RECONCILED,
        ).first()

        if settled_vd:
            settled_amt = Decimal("500000")
            db.session.add(GiaoDich(
                MaTaiXe       = sample_driver.MaTaiXe,
                MaAdmin       = admin.MaAdmin,
                SoTien        = settled_amt,
                SoTienThucThu = settled_amt,
                GhiChu        = "Đối soát ca chiều — khớp tiền.",
                ThoiGian      = datetime.utcnow() - timedelta(hours=2),
            ))
            # Reset wallet for this driver's reconciled amount
            sample_driver.SoDuVi = max(Decimal("0"), sample_driver.SoDuVi - settled_amt)

        db.session.commit()

        print()
        print("══════════════════════════════════════════════")
        print("  SEED hoàn tất! Thông tin đăng nhập:")
        print("  Admin:    admin@vandon.com  /  admin123")
        print("  Tài xế 1: 0911111111        /  driver123")
        print("  Tài xế 2: 0922222222        /  driver123")
        print("  Tài xế 3: 0933333333        /  driver123")
        print("══════════════════════════════════════════════")


if __name__ == "__main__":
    seed()
