"""
app.py — Main Flask application
Hệ thống Quản lý Vận đơn và Đối soát Tài chính Chặng cuối
Last-Mile Waybill Management and Financial Reconciliation System
"""
import os
import random
import string
from datetime import datetime, date, timedelta
from decimal import Decimal
from functools import wraps

import bcrypt
from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from sqlalchemy import func
from werkzeug.utils import secure_filename

from models import Admin, CauHinhHeThong, GiaoDich, LichSuLog, TaiXe, VanDon, db

# ──────────────────────────────────────────────────────────────────────────────
# App factory / config
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "vandon-secret-key-change-in-production-2024"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///vandon.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ── Task 1: File-upload configuration ──────────────────────────────────────────
_UPLOAD_BASE = os.path.join(os.path.dirname(__file__), "static", "uploads", "proofs")
app.config["UPLOAD_FOLDER"]   = _UPLOAD_BASE
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024   # 10 MB hard limit
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(_UPLOAD_BASE, exist_ok=True)               # create folder on startup

db.init_app(app)


# ──────────────────────────────────────────────────────────────────────────────
# Template filters
# ──────────────────────────────────────────────────────────────────────────────
@app.template_filter("vnd")
def vnd_format(value):
    """Format a numeric value as Vietnamese Dong."""
    if value is None:
        return "0 ₫"
    try:
        return f"{int(value):,} ₫".replace(",", ".")
    except (TypeError, ValueError):
        return "0 ₫"


@app.template_filter("dt")
def datetime_format(value):
    if not value:
        return "—"
    return value.strftime("%d/%m/%Y %H:%M")


@app.template_filter("badge")
def status_badge(status):
    """Return Bootstrap badge background class for a given status string."""
    mapping = {
        "Chờ điều phối": "secondary",
        "Đang đi giao":  "warning",
        "Thành công":    "success",
        "Giao thất bại": "danger",
        "Đã đối soát":   "primary",
    }
    return mapping.get(status, "secondary")


@app.template_filter("badge_icon")
def status_badge_icon(status):
    mapping = {
        "Chờ điều phối": "bi-clock",
        "Đang đi giao":  "bi-truck",
        "Thành công":    "bi-check-circle-fill",
        "Giao thất bại": "bi-x-circle-fill",
        "Đã đối soát":   "bi-shield-check",
    }
    return mapping.get(status, "bi-circle")


# ──────────────────────────────────────────────────────────────────────────────
# Auth decorators
# ──────────────────────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_type") != "admin":
            flash("Bạn cần đăng nhập với quyền Admin.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def driver_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_type") != "driver":
            flash("Bạn cần đăng nhập với quyền Tài xế.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────────────
def generate_waybill_id() -> str:
    """Auto-generate unique MaVanDon: VD + YYYYMMDD + 5 random digits."""
    prefix = "VD" + datetime.utcnow().strftime("%Y%m%d")
    for _ in range(20):
        candidate = prefix + "".join(random.choices(string.digits, k=5))
        if not VanDon.query.get(candidate):
            return candidate
    raise RuntimeError("Unable to generate unique MaVanDon after 20 attempts.")


def calculate_shipping_fee(tien_cod: Decimal) -> Decimal:
    """
    Shipping fee pulled from CauHinhHeThong if available, else hardcoded fallback.
    formula: base_fee + (cod_rate × TienCOD), minimum = base_fee.
    """
    try:
        base_row = CauHinhHeThong.query.filter_by(key="phi_co_ban").first()
        rate_row = CauHinhHeThong.query.filter_by(key="ty_le_cod").first()
        base = Decimal(base_row.value if base_row else "20000")
        rate = Decimal(rate_row.value if rate_row else "0.01")
    except Exception:
        base, rate = Decimal("20000"), Decimal("0.01")
    fee = base + Decimal(str(tien_cod)) * rate
    return max(fee, base).quantize(Decimal("1"))


# ── Task 1 helpers ──────────────────────────────────────────────────────────────
def allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed image extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_proof_photo(file, ma_van_don: str) -> str:
    """
    Save the uploaded FileStorage object to UPLOAD_FOLDER.
    Returns the stored filename (not full path).
    Raises ValueError on bad extension.
    """
    if not allowed_file(file.filename):
        raise ValueError("Định dạng ảnh không hợp lệ. Chỉ chấp nhận PNG, JPG, GIF, WEBP.")
    ext      = file.filename.rsplit(".", 1)[1].lower()
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = secure_filename(f"{ma_van_don}_{ts}.{ext}")
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return filename


# ── Task 2 helper ──────────────────────────────────────────────────────────────
def get_setting(key: str, default: str = "") -> str:
    """Fetch a single setting value by key; return default if not found."""
    row = CauHinhHeThong.query.filter_by(key=key).first()
    return row.value if row else default


# ──────────────────────────────────────────────────────────────────────────────
# Root / Auth routes
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    utype = session.get("user_type")
    if utype == "admin":
        return redirect(url_for("admin_dashboard"))
    if utype == "driver":
        return redirect(url_for("driver_tasks"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "").encode("utf-8")

        # ── Check Admin (by Email) ──
        admin = Admin.query.filter_by(Email=identifier).first()
        if admin and admin.MatKhau and bcrypt.checkpw(password, admin.MatKhau.encode("utf-8")):
            session.clear()
            session["user_id"]   = admin.MaAdmin
            session["user_type"] = "admin"
            session["user_name"] = admin.TenAdmin
            return redirect(url_for("admin_dashboard"))

        # ── Check Driver (by Phone) ──
        driver = TaiXe.query.filter_by(DienThoai=identifier).first()
        if driver and driver.MatKhau and bcrypt.checkpw(password, driver.MatKhau.encode("utf-8")):
            session.clear()
            session["user_id"]   = driver.MaTaiXe
            session["user_type"] = "driver"
            session["user_name"] = driver.TenTaiXe
            return redirect(url_for("driver_tasks"))

        # Detailed debug hint (only visible in dev — remove in production)
        if driver and not driver.MatKhau:
            error = "Tài khoản tài xế chưa có mật khẩu. Hãy chạy: python seed.py"
        else:
            error = "Email / SĐT hoặc mật khẩu không đúng!"

    return render_template("login.html", error=error)


@app.route("/track", methods=["GET", "POST"])
def track_waybill():
    """
    Public Track & Trace — no login required.
    Customers enter MaVanDon to see package status + full history timeline.
    """
    waybill = None
    logs    = []
    error   = None
    query   = (
        request.form.get("ma_van_don", "").strip()
        or request.args.get("id", "").strip()
    ).upper()

    if query:
        waybill = db.session.get(VanDon, query)
        if waybill:
            logs = (
                LichSuLog.query
                .filter_by(MaVanDon=query)
                .order_by(LichSuLog.ThoiGian.asc())
                .all()
            )
            # Mask recipient phone for privacy (show only last 3 digits)
            parts = waybill.ThongTinNhan.split(" | ")
            masked_parts = []
            for i, p in enumerate(parts):
                if i == 1 and len(p) >= 4:          # phone field
                    p = "*" * (len(p) - 3) + p[-3:]
                masked_parts.append(p)
            waybill._masked_info = masked_parts
        else:
            error = f"Không tìm thấy vận đơn với mã <strong>{query}</strong>. Vui lòng kiểm tra lại."

    return render_template(
        "tracking.html",
        waybill=waybill,
        logs=logs,
        error=error,
        query=query,
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất thành công.", "info")
    return redirect(url_for("login"))


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN — Dashboard
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    total_orders       = VanDon.query.count()
    total_success      = VanDon.query.filter(
        VanDon.TrangThai.in_(["Thành công", "Đã đối soát"])
    ).count()
    pending_dispatch   = VanDon.query.filter_by(TrangThai="Chờ điều phối").count()
    delivering         = VanDon.query.filter_by(TrangThai="Đang đi giao").count()
    failed             = VanDon.query.filter_by(TrangThai="Giao thất bại").count()
    total_cod_holding  = db.session.query(func.sum(TaiXe.SoDuVi)).scalar() or Decimal("0")
    recent_orders      = VanDon.query.order_by(VanDon.NgayTao.desc()).limit(8).all()

    # Chart: orders created per day — last 7 days
    chart_labels, chart_success, chart_failed = [], [], []
    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        s = VanDon.query.filter(
            func.date(VanDon.NgayTao) == day_str,
            VanDon.TrangThai.in_(["Thành công", "Đã đối soát"])
        ).count()
        f = VanDon.query.filter(
            func.date(VanDon.NgayTao) == day_str,
            VanDon.TrangThai == "Giao thất bại"
        ).count()
        chart_labels.append(day.strftime("%d/%m"))
        chart_success.append(s)
        chart_failed.append(f)

    return render_template(
        "admin/dashboard.html",
        total_orders=total_orders,
        total_success=total_success,
        pending_dispatch=pending_dispatch,
        delivering=delivering,
        failed=failed,
        total_cod_holding=total_cod_holding,
        recent_orders=recent_orders,
        chart_labels=chart_labels,
        chart_success=chart_success,
        chart_failed=chart_failed,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN — Waybill Management
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/admin/waybills")
@admin_required
def admin_waybills():
    status_filter = request.args.get("status", "")
    driver_filter = request.args.get("driver", "")
    search        = request.args.get("search", "").strip()
    page          = request.args.get("page", 1, type=int)

    query = VanDon.query
    if status_filter:
        query = query.filter_by(TrangThai=status_filter)
    if driver_filter:
        query = query.filter_by(MaTaiXe=int(driver_filter))
    if search:
        query = query.filter(
            db.or_(
                VanDon.MaVanDon.ilike(f"%{search}%"),
                VanDon.ThongTinNhan.ilike(f"%{search}%"),
            )
        )

    pagination = query.order_by(VanDon.NgayTao.desc()).paginate(page=page, per_page=20, error_out=False)
    drivers     = TaiXe.query.order_by(TaiXe.TenTaiXe).all()
    statuses    = ["Chờ điều phối", "Đang đi giao", "Thành công", "Giao thất bại", "Đã đối soát"]

    return render_template(
        "admin/waybills.html",
        pagination=pagination,
        waybills=pagination.items,
        drivers=drivers,
        statuses=statuses,
        status_filter=status_filter,
        driver_filter=driver_filter,
        search=search,
    )


@app.route("/admin/waybills/create", methods=["GET", "POST"])
@admin_required
def admin_create_waybill():
    drivers = TaiXe.query.order_by(TaiXe.TenTaiXe).all()

    if request.method == "POST":
        ten_nhan    = request.form.get("ten_nhan",    "").strip()
        sdt_nhan    = request.form.get("sdt_nhan",    "").strip()
        dia_chi     = request.form.get("dia_chi",     "").strip()
        raw_cod     = request.form.get("tien_cod",    "0").strip() or "0"

        if not all([ten_nhan, sdt_nhan, dia_chi]):
            flash("Vui lòng điền đầy đủ thông tin người nhận!", "danger")
            return render_template("admin/waybill_create.html", drivers=drivers)

        tien_cod     = Decimal(raw_cod)
        cuoc_phi     = calculate_shipping_fee(tien_cod)
        thong_tin    = f"{ten_nhan} | {sdt_nhan} | {dia_chi}"
        ma_van_don   = generate_waybill_id()

        try:
            van_don = VanDon(
                MaVanDon     = ma_van_don,
                ThongTinNhan = thong_tin,
                TienCOD      = tien_cod,
                CuocPhi      = cuoc_phi,
                TrangThai    = VanDon.STATUS_PENDING,
                MaAdmin      = session["user_id"],
            )
            db.session.add(van_don)

            log = LichSuLog(
                MaVanDon     = ma_van_don,
                TrangThaiCu  = None,
                TrangThaiMoi = VanDon.STATUS_PENDING,
                GhiChu       = f"Tạo vận đơn mới bởi {session['user_name']}",
            )
            db.session.add(log)
            db.session.commit()

            flash(f"✔ Tạo vận đơn thành công! Mã: {ma_van_don}", "success")
            return redirect(url_for("admin_waybill_detail", ma_van_don=ma_van_don))

        except Exception as exc:
            db.session.rollback()
            flash(f"Lỗi tạo vận đơn: {exc}", "danger")

    return render_template("admin/waybill_create.html", drivers=drivers)


@app.route("/admin/waybills/<ma_van_don>")
@admin_required
def admin_waybill_detail(ma_van_don):
    van_don = VanDon.query.get_or_404(ma_van_don)
    logs    = LichSuLog.query.filter_by(MaVanDon=ma_van_don).order_by(LichSuLog.ThoiGian.asc()).all()
    drivers = TaiXe.query.order_by(TaiXe.TenTaiXe).all()
    parts   = van_don.ThongTinNhan.split(" | ")
    return render_template(
        "admin/waybill_detail.html",
        van_don=van_don,
        logs=logs,
        drivers=drivers,
        parts=parts,
    )


@app.route("/admin/waybills/<ma_van_don>/assign", methods=["POST"])
@admin_required
def admin_assign_driver(ma_van_don):
    """Workflow B: Assign / re-assign a driver to a waybill."""
    van_don   = VanDon.query.get_or_404(ma_van_don)
    driver_id = request.form.get("driver_id", type=int)

    if van_don.TrangThai not in [VanDon.STATUS_PENDING, VanDon.STATUS_DELIVERING]:
        return jsonify({"ok": False, "msg": "Không thể điều phối vận đơn này."}), 400

    driver = TaiXe.query.get(driver_id)
    if not driver:
        return jsonify({"ok": False, "msg": "Tài xế không tồn tại."}), 404

    try:
        old_status      = van_don.TrangThai
        van_don.MaTaiXe = driver.MaTaiXe
        van_don.TrangThai = VanDon.STATUS_DELIVERING

        db.session.add(LichSuLog(
            MaVanDon     = ma_van_don,
            TrangThaiCu  = old_status,
            TrangThaiMoi = VanDon.STATUS_DELIVERING,
            GhiChu       = f"Điều phối cho tài xế: {driver.TenTaiXe} ({driver.DienThoai})",
        ))
        db.session.commit()
        return jsonify({"ok": True, "msg": f"Đã điều phối cho {driver.TenTaiXe}",
                        "driver_name": driver.TenTaiXe, "new_status": van_don.TrangThai})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "msg": str(exc)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN — Driver Management
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/admin/drivers")
@admin_required
def admin_drivers():
    """
    Pre-compute per-driver statistics in Python.
    NEVER call .filter_by() or .count() inside Jinja2 templates with SQLAlchemy 2.x.
    """
    drivers_raw = TaiXe.query.order_by(TaiXe.TenTaiXe).all()
    driver_list = []
    for d in drivers_raw:
        active_cnt     = VanDon.query.filter_by(MaTaiXe=d.MaTaiXe, TrangThai=VanDon.STATUS_DELIVERING).count()
        success_cnt    = VanDon.query.filter_by(MaTaiXe=d.MaTaiXe, TrangThai=VanDon.STATUS_SUCCESS).count()
        reconciled_cnt = VanDon.query.filter_by(MaTaiXe=d.MaTaiXe, TrangThai=VanDon.STATUS_RECONCILED).count()
        driver_list.append({
            "obj":            d,
            "active_count":   active_cnt,
            "done_count":     success_cnt + reconciled_cnt,
            "has_pending_cod": d.SoDuVi > 0,
        })
    total_cod = db.session.query(func.sum(TaiXe.SoDuVi)).scalar() or Decimal("0")
    return render_template("admin/drivers.html",
                           driver_list=driver_list,
                           total_cod=total_cod)


@app.route("/admin/drivers/create", methods=["GET", "POST"])
@admin_required
def admin_create_driver():
    if request.method == "POST":
        ten       = request.form.get("ten_tai_xe",  "").strip()
        phone     = request.form.get("dien_thoai",  "").strip()
        khu_vuc   = request.form.get("khu_vuc",     "").strip()
        password  = request.form.get("mat_khau",    "").strip()

        if not all([ten, phone, password]):
            flash("Vui lòng điền đầy đủ họ tên, SĐT và mật khẩu!", "danger")
            return render_template("admin/driver_create.html")

        if TaiXe.query.filter_by(DienThoai=phone).first():
            flash("Số điện thoại này đã tồn tại trong hệ thống!", "danger")
            return render_template("admin/driver_create.html")

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            driver = TaiXe(
                TenTaiXe  = ten,
                DienThoai = phone,
                MatKhau   = hashed,
                KhuVuc    = khu_vuc,
                SoDuVi    = Decimal("0.00"),
            )
            db.session.add(driver)
            db.session.commit()
            flash(f"✔ Tài xế {ten} đã được tạo thành công!", "success")
            return redirect(url_for("admin_drivers"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Lỗi: {exc}", "danger")

    return render_template("admin/driver_create.html")


@app.route("/admin/drivers/<int:driver_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_driver(driver_id):
    driver = db.session.get(TaiXe, driver_id)
    if not driver:
        flash("Tài xế không tồn tại.", "danger")
        return redirect(url_for("admin_drivers"))

    if request.method == "POST":
        ten      = request.form.get("ten_tai_xe",  "").strip()
        phone    = request.form.get("dien_thoai",  "").strip()
        khu_vuc  = request.form.get("khu_vuc",     "").strip()
        new_pw   = request.form.get("mat_khau",    "").strip()

        if not all([ten, phone]):
            flash("Họ tên và SĐT không được để trống!", "danger")
            return render_template("admin/driver_edit.html", driver=driver)

        # Check phone uniqueness (exclude self)
        conflict = TaiXe.query.filter(
            TaiXe.DienThoai == phone, TaiXe.MaTaiXe != driver_id
        ).first()
        if conflict:
            flash("Số điện thoại này đã được dùng bởi tài xế khác!", "danger")
            return render_template("admin/driver_edit.html", driver=driver)

        driver.TenTaiXe  = ten
        driver.DienThoai = phone
        driver.KhuVuc    = khu_vuc
        if new_pw:
            driver.MatKhau = bcrypt.hashpw(
                new_pw.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
        try:
            db.session.commit()
            flash(f"✔ Đã cập nhật thông tin tài xế {ten}.", "success")
            return redirect(url_for("admin_drivers"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Lỗi lưu dữ liệu: {exc}", "danger")

    return render_template("admin/driver_edit.html", driver=driver)


@app.route("/admin/drivers/<int:driver_id>/delete", methods=["POST"])
@admin_required
def admin_delete_driver(driver_id):
    """Delete driver — guarded: no active deliveries, no pending COD."""
    driver = db.session.get(TaiXe, driver_id)
    if not driver:
        return jsonify({"ok": False, "msg": "Tài xế không tồn tại."}), 404

    active_cnt = VanDon.query.filter_by(
        MaTaiXe=driver_id, TrangThai=VanDon.STATUS_DELIVERING
    ).count()
    if active_cnt > 0:
        return jsonify({
            "ok": False,
            "msg": f"Không thể xóa! Tài xế đang có {active_cnt} vận đơn đang giao."
        }), 400

    if driver.SoDuVi > 0:
        from decimal import Decimal
        return jsonify({
            "ok": False,
            "msg": f"Không thể xóa! Tài xế đang giữ {int(driver.SoDuVi):,} ₫ COD chưa quyết toán.".replace(",", ".")
        }), 400

    name = driver.TenTaiXe
    try:
        # Nullify FK references on waybills first
        VanDon.query.filter_by(MaTaiXe=driver_id).update({"MaTaiXe": None})
        db.session.delete(driver)
        db.session.commit()
        return jsonify({"ok": True, "msg": f"Đã xóa tài xế {name}."})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "msg": str(exc)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN — Financial Reconciliation (Workflow D)
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/admin/reconciliation")
@admin_required
def admin_reconciliation():
    import csv, io
    all_drivers    = TaiXe.query.order_by(TaiXe.TenTaiXe).all()
    active_drivers = [d for d in all_drivers if d.SoDuVi > 0]

    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()

    tx_query = (
        db.session.query(GiaoDich, TaiXe, Admin)
        .join(TaiXe,  GiaoDich.MaTaiXe == TaiXe.MaTaiXe)
        .join(Admin,  GiaoDich.MaAdmin  == Admin.MaAdmin)
    )
    if date_from:
        try:
            tx_query = tx_query.filter(
                GiaoDich.ThoiGian >= datetime.strptime(date_from, "%Y-%m-%d")
            )
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            tx_query = tx_query.filter(GiaoDich.ThoiGian < dt_to)
        except ValueError:
            pass

    transactions = tx_query.order_by(GiaoDich.ThoiGian.desc()).limit(100).all()

    # Summary stats for filtered period
    total_settled = sum(float(gd.SoTien) for gd, _, __ in transactions)
    total_actual  = sum(float(gd.SoTienThucThu or 0) for gd, _, __ in transactions)

    return render_template(
        "admin/reconciliation.html",
        active_drivers=active_drivers,
        all_drivers=all_drivers,
        transactions=transactions,
        date_from=date_from,
        date_to=date_to,
        total_settled=total_settled,
        total_actual=total_actual,
    )


@app.route("/admin/reconciliation/export")
@admin_required
def admin_export_reconciliation():
    """Export filtered settlement history as CSV (Excel-friendly UTF-8 BOM)."""
    import csv, io
    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to",   "").strip()

    tx_query = (
        db.session.query(GiaoDich, TaiXe, Admin)
        .join(TaiXe,  GiaoDich.MaTaiXe == TaiXe.MaTaiXe)
        .join(Admin,  GiaoDich.MaAdmin  == Admin.MaAdmin)
    )
    if date_from:
        try:
            tx_query = tx_query.filter(
                GiaoDich.ThoiGian >= datetime.strptime(date_from, "%Y-%m-%d")
            )
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            tx_query = tx_query.filter(GiaoDich.ThoiGian < dt_to)
        except ValueError:
            pass

    rows = tx_query.order_by(GiaoDich.ThoiGian.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Mã GD", "Thời gian", "Tài xế", "SĐT tài xế",
        "Admin xác nhận", "Hệ thống (₫)", "Thực thu (₫)",
        "Chênh lệch (₫)", "Ghi chú"
    ])
    for gd, tx, adm in rows:
        diff = float(gd.SoTienThucThu or 0) - float(gd.SoTien)
        writer.writerow([
            gd.MaGiaoDich,
            gd.ThoiGian.strftime("%d/%m/%Y %H:%M"),
            tx.TenTaiXe, tx.DienThoai,
            adm.TenAdmin,
            f"{float(gd.SoTien):,.0f}",
            f"{float(gd.SoTienThucThu or 0):,.0f}",
            f"{diff:,.0f}",
            gd.GhiChu or "",
        ])

    fname = f"doi_soat_{date_from or 'all'}_{date_to or 'all'}.csv"
    return app.response_class(
        "\ufeff" + output.getvalue(),   # BOM → Excel opens Vietnamese correctly
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"}
    )


@app.route("/admin/reconciliation/<int:driver_id>/info")
@admin_required
def admin_reconciliation_info(driver_id):
    """AJAX endpoint: return driver reconciliation details as JSON."""
    driver = TaiXe.query.get_or_404(driver_id)
    waybills = VanDon.query.filter_by(
        MaTaiXe=driver_id, TrangThai=VanDon.STATUS_SUCCESS
    ).all()
    return jsonify({
        "driver_id":   driver.MaTaiXe,
        "driver_name": driver.TenTaiXe,
        "khu_vuc":     driver.KhuVuc or "—",
        "so_du_vi":    float(driver.SoDuVi),
        "van_don_count": len(waybills),
        "waybills": [
            {"id": w.MaVanDon, "cod": float(w.TienCOD),
             "info": w.ThongTinNhan.split(" | ")[0]}
            for w in waybills
        ],
    })


@app.route("/admin/reconciliation/<int:driver_id>/confirm", methods=["POST"])
@admin_required
def admin_confirm_reconciliation(driver_id):
    """Workflow D: Atomic financial reconciliation settlement."""
    driver          = TaiXe.query.get_or_404(driver_id)
    raw_thuc_thu    = request.form.get("so_tien_thuc_thu", "0").strip() or "0"
    ghi_chu         = request.form.get("ghi_chu", "").strip()

    so_tien_thuc_thu = Decimal(raw_thuc_thu)
    waybills = VanDon.query.filter_by(
        MaTaiXe=driver_id, TrangThai=VanDon.STATUS_SUCCESS
    ).all()

    if not waybills:
        flash("Không có vận đơn 'Thành công' nào cần đối soát cho tài xế này!", "warning")
        return redirect(url_for("admin_reconciliation"))

    try:
        # 1. Create permanent GiaoDich record
        discrepancy = so_tien_thuc_thu - driver.SoDuVi
        note = ghi_chu or (
            f"Đối soát {len(waybills)} vận đơn. "
            f"Chênh lệch: {int(discrepancy):,} ₫".replace(",", ".")
        )
        giao_dich = GiaoDich(
            MaTaiXe       = driver_id,
            MaAdmin       = session["user_id"],
            SoTien        = driver.SoDuVi,
            SoTienThucThu = so_tien_thuc_thu,
            GhiChu        = note,
        )
        db.session.add(giao_dich)

        # 2. Mark each successful waybill as reconciled
        for w in waybills:
            old = w.TrangThai
            w.TrangThai = VanDon.STATUS_RECONCILED
            db.session.add(LichSuLog(
                MaVanDon     = w.MaVanDon,
                TrangThaiCu  = old,
                TrangThaiMoi = VanDon.STATUS_RECONCILED,
                GhiChu       = f"Đối soát bởi {session['user_name']}",
            ))

        # 3. Reset driver's cash wallet
        driver.SoDuVi = Decimal("0.00")

        db.session.commit()
        flash(
            f"✔ Đối soát thành công! "
            f"Đã xử lý {len(waybills)} vận đơn, "
            f"thu {int(so_tien_thuc_thu):,} ₫.".replace(",", "."),
            "success",
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"Lỗi đối soát: {exc}", "danger")

    return redirect(url_for("admin_reconciliation"))


# ──────────────────────────────────────────────────────────────────────────────
# DRIVER — Task Management (Workflows C)
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/driver/tasks")
@driver_required
def driver_tasks():
    driver_id    = session["user_id"]
    driver       = TaiXe.query.get(driver_id)
    tab          = request.args.get("tab", "active")
    # Pre-compute badge count so template needs no SQLAlchemy calls
    active_count = VanDon.query.filter_by(MaTaiXe=driver_id, TrangThai=VanDon.STATUS_DELIVERING).count()

    if tab == "active":
        waybills = VanDon.query.filter_by(
            MaTaiXe=driver_id, TrangThai=VanDon.STATUS_DELIVERING
        ).order_by(VanDon.NgayTao.desc()).all()
    elif tab == "done":
        waybills = VanDon.query.filter(
            VanDon.MaTaiXe == driver_id,
            VanDon.TrangThai.in_([VanDon.STATUS_SUCCESS, VanDon.STATUS_FAILED,
                                   VanDon.STATUS_RECONCILED])
        ).order_by(VanDon.NgayTao.desc()).limit(50).all()
    else:
        waybills = VanDon.query.filter_by(MaTaiXe=driver_id).order_by(VanDon.NgayTao.desc()).all()

    return render_template("driver/tasks.html",
                           driver=driver,
                           waybills=waybills,
                           tab=tab,
                           active_count=active_count)


@app.route("/driver/tasks/<ma_van_don>")
@driver_required
def driver_task_detail(ma_van_don):
    driver_id = session["user_id"]
    van_don   = VanDon.query.filter_by(MaVanDon=ma_van_don, MaTaiXe=driver_id).first_or_404()
    logs      = LichSuLog.query.filter_by(MaVanDon=ma_van_don).order_by(LichSuLog.ThoiGian.asc()).all()
    parts     = van_don.ThongTinNhan.split(" | ")
    return render_template("driver/update.html", van_don=van_don, logs=logs, parts=parts)


@app.route("/driver/tasks/<ma_van_don>/update", methods=["POST"])
@driver_required
def driver_update_status(ma_van_don):
    """
    Workflow C: Driver updates waybill status.
    TASK 1 EXTENDED: Accepts optional proof-of-delivery photo (multipart/form-data).
    CRITICAL: COD reconciliation logic unchanged — SoDuVi only modified on success.
    """
    driver_id = session["user_id"]
    van_don   = VanDon.query.filter_by(MaVanDon=ma_van_don, MaTaiXe=driver_id).first_or_404()

    # Guard: only 'Đang đi giao' can be updated
    if van_don.TrangThai != VanDon.STATUS_DELIVERING:
        flash("Vận đơn này đã được xử lý và không thể cập nhật lại!", "warning")
        return redirect(url_for("driver_task_detail", ma_van_don=ma_van_don))

    action = request.form.get("action")
    ly_do  = request.form.get("ly_do", "").strip()

    try:
        old_status = van_don.TrangThai

        if action == "success":
            # ── Task 1: handle proof photo upload (optional) ────────
            photo_file = request.files.get("hinh_anh_minh_chung")
            has_photo  = False
            if photo_file and photo_file.filename:
                try:
                    filename = save_proof_photo(photo_file, ma_van_don)
                    van_don.HinhAnhMinhChung = filename
                    has_photo = True
                except (ValueError, OSError) as photo_err:
                    flash(f"⚠ Lưu ảnh thất bại: {photo_err}. Trạng thái vẫn được cập nhật.", "warning")

            # ── Core COD logic (UNCHANGED) ──────────────────────────
            van_don.TrangThai = VanDon.STATUS_SUCCESS
            driver = db.session.get(TaiXe, driver_id)
            driver.SoDuVi = driver.SoDuVi + van_don.TienCOD

            ghi_chu = "Tài xế xác nhận giao hàng thành công."
            if has_photo:
                ghi_chu += " [Có ảnh minh chứng]"

            db.session.add(LichSuLog(
                MaVanDon     = ma_van_don,
                TrangThaiCu  = old_status,
                TrangThaiMoi = VanDon.STATUS_SUCCESS,
                GhiChu       = ghi_chu,
            ))
            db.session.commit()
            # Fix: use Python vnd_format() not Jinja2 filter in flash()
            cod_fmt = vnd_format(van_don.TienCOD)
            flash(f"✔ Giao hàng thành công! Ví COD đã được cộng {cod_fmt}.", "success")

        elif action == "fail":
            if not ly_do:
                flash("Bạn phải nhập lý do khi báo giao thất bại!", "danger")
                return redirect(url_for("driver_task_detail", ma_van_don=ma_van_don))
            van_don.TrangThai = VanDon.STATUS_FAILED
            # SoDuVi NOT modified for failed delivery (COD logic preserved)
            db.session.add(LichSuLog(
                MaVanDon     = ma_van_don,
                TrangThaiCu  = old_status,
                TrangThaiMoi = VanDon.STATUS_FAILED,
                GhiChu       = f"Lý do thất bại: {ly_do}",
            ))
            db.session.commit()
            flash("Đã cập nhật trạng thái giao thất bại.", "info")

        else:
            flash("Hành động không hợp lệ.", "danger")
            return redirect(url_for("driver_task_detail", ma_van_don=ma_van_don))

    except Exception as exc:
        db.session.rollback()
        flash(f"Lỗi cập nhật: {exc}", "danger")
        return redirect(url_for("driver_task_detail", ma_van_don=ma_van_don))

    return redirect(url_for("driver_tasks"))


@app.route("/uploads/proofs/<filename>")
@admin_required
def serve_proof(filename):
    """Serve proof photos — admin-only to protect privacy."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN — System Settings (Task 2)
# ──────────────────────────────────────────────────────────────────────────────

# Default settings seeded on first run
_DEFAULT_SETTINGS = [
    ("phi_co_ban",           "20000",           "number",  "Phí cơ bản (₫) — áp dụng cho mọi vận đơn"),
    ("ty_le_cod",            "0.01",            "number",  "Tỉ lệ phí COD (thập phân, 0.01 = 1%)"),
    ("phi_toi_da",           "500000",          "number",  "Phí giao hàng tối đa (₫)"),
    ("ten_cong_ty",          "VanDon Express",  "string",  "Tên công ty hiển thị trên hệ thống"),
    ("hotline",              "1900 xxxx",       "string",  "Hotline hỗ trợ khách hàng"),
    ("email_lien_he",        "info@vandon.com", "string",  "Email liên hệ hỗ trợ"),
    ("so_ngay_luu_log",      "90",              "number",  "Số ngày lưu lịch sử log vận đơn"),
    ("cho_phep_upload_anh",  "true",            "boolean", "Cho phép tài xế upload ảnh minh chứng"),
    ("kich_thuoc_anh_toi_da","10",              "number",  "Kích thước ảnh tối đa (MB)"),
    ("tu_dong_doi_soat",     "false",           "boolean", "Tự động đối soát sau khi giao thành công"),
]


def seed_settings():
    """Insert default settings; skip any key that already exists."""
    for key, value, dtype, desc in _DEFAULT_SETTINGS:
        if not CauHinhHeThong.query.filter_by(key=key).first():
            db.session.add(CauHinhHeThong(
                key=key, value=value, data_type=dtype, description=desc
            ))
    db.session.commit()


@app.route("/admin/settings")
@admin_required
def admin_settings():
    settings = CauHinhHeThong.query.order_by(CauHinhHeThong.id).all()
    return render_template("admin/settings.html", settings=settings)


@app.route("/admin/settings/update", methods=["POST"])
@admin_required
def admin_settings_update():
    """Save all submitted settings in one atomic transaction."""
    try:
        all_settings = CauHinhHeThong.query.all()
        updated = 0
        for s in all_settings:
            form_val = request.form.get(f"setting_{s.key}")
            if form_val is not None:
                new_val = form_val.strip()
                # Boolean checkboxes: present = true, absent = false
                if s.data_type == "boolean":
                    new_val = "true"
                if s.value != new_val:
                    s.value      = new_val
                    s.updated_at = datetime.utcnow()
                    updated += 1

        # Handle unchecked booleans (not present in form at all)
        for s in all_settings:
            if s.data_type == "boolean" and f"setting_{s.key}" not in request.form:
                if s.value != "false":
                    s.value      = "false"
                    s.updated_at = datetime.utcnow()
                    updated += 1

        db.session.commit()
        flash(f"✔ Đã lưu {updated} thay đổi cấu hình hệ thống.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Lỗi lưu cấu hình: {exc}", "danger")
    return redirect(url_for("admin_settings"))


# ──────────────────────────────────────────────────────────────────────────────
# Init DB + Default Seed
# ──────────────────────────────────────────────────────────────────────────────
def init_db():
    """Create all tables; insert defaults if none exist."""
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")
            db.session.add(Admin(TenAdmin="Super Admin", Email="admin@vandon.com", MatKhau=pw))
            db.session.commit()
            print("[INIT] Default admin → admin@vandon.com / admin123")
        seed_settings()
        print("[INIT] System settings seeded.")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
