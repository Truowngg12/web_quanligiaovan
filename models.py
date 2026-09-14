"""
models.py — SQLAlchemy ORM models
Exactly implements the 5-table schema from the graduation project spec.
Two extra fields added beyond strict spec (noted with # EXTENDED comments):
  - TaiXe.MatKhau  → required for driver RBAC login
  - LichSuLog.GhiChu → required to store failure reasons
  - GiaoDich.SoTienThucThu / GhiChu → required for settlement reconciliation
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# ─── Table 1: ADMIN ────────────────────────────────────────────────────────────
class Admin(db.Model):
    __tablename__ = "ADMIN"

    MaAdmin  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TenAdmin = db.Column(db.String(100), nullable=False)
    Email    = db.Column(db.String(100), unique=True, nullable=False)
    MatKhau  = db.Column(db.String(255), nullable=False)   # Bcrypt hash

    # back-references populated by VanDon / GiaoDich relationships below
    waybills     = db.relationship("VanDon",    back_populates="admin",  lazy="dynamic")
    transactions = db.relationship("GiaoDich",  back_populates="admin",  lazy="dynamic")

    def __repr__(self):
        return f"<Admin {self.Email}>"


# ─── Table 2: TAI_XE ───────────────────────────────────────────────────────────
class TaiXe(db.Model):
    __tablename__ = "TAI_XE"

    MaTaiXe   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TenTaiXe  = db.Column(db.String(100), nullable=False)
    DienThoai = db.Column(db.String(15), unique=True, nullable=False)
    MatKhau   = db.Column(db.String(255), nullable=False)  # EXTENDED: needed for login
    KhuVuc    = db.Column(db.String(100))
    SoDuVi    = db.Column(db.Numeric(15, 2), nullable=False, default=0.00)
    # SoDuVi: running COD cash balance the driver is physically holding

    waybills     = db.relationship("VanDon",   back_populates="driver", lazy="dynamic")
    transactions = db.relationship("GiaoDich", back_populates="driver", lazy="dynamic")

    def __repr__(self):
        return f"<TaiXe {self.TenTaiXe} ({self.DienThoai})>"


# ─── Table 3: VAN_DON ──────────────────────────────────────────────────────────
class VanDon(db.Model):
    __tablename__ = "VAN_DON"

    MaVanDon            = db.Column(db.String(20), primary_key=True)
    ThongTinNhan        = db.Column(db.Text, nullable=False)
    TienCOD             = db.Column(db.Numeric(15, 2), nullable=False, default=0.00)
    CuocPhi             = db.Column(db.Numeric(15, 2), nullable=False)
    TrangThai           = db.Column(db.String(50), nullable=False, default="Chờ điều phối")
    MaAdmin             = db.Column(db.Integer, db.ForeignKey("ADMIN.MaAdmin"),   nullable=False)
    MaTaiXe             = db.Column(db.Integer, db.ForeignKey("TAI_XE.MaTaiXe"), nullable=True)
    NgayTao             = db.Column(db.DateTime, default=datetime.utcnow)
    # TASK 1 EXTENDED: Proof-of-delivery photo — stores filename inside UPLOAD_FOLDER
    HinhAnhMinhChung    = db.Column(db.String(255), nullable=True)

    admin  = db.relationship("Admin",  back_populates="waybills")
    driver = db.relationship("TaiXe",  back_populates="waybills")
    logs   = db.relationship(
        "LichSuLog",
        back_populates="waybill",
        order_by="LichSuLog.ThoiGian",
        lazy="dynamic",
    )

    # Valid statuses (state machine)
    STATUS_PENDING    = "Chờ điều phối"
    STATUS_DELIVERING = "Đang đi giao"
    STATUS_SUCCESS    = "Thành công"
    STATUS_FAILED     = "Giao thất bại"
    STATUS_RECONCILED = "Đã đối soát"

    def __repr__(self):
        return f"<VanDon {self.MaVanDon} [{self.TrangThai}]>"


# ─── Table 4: LICH_SU_LOG ──────────────────────────────────────────────────────
class LichSuLog(db.Model):
    __tablename__ = "LICH_SU_LOG"

    MaLog       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    MaVanDon    = db.Column(db.String(20), db.ForeignKey("VAN_DON.MaVanDon"), nullable=False)
    TrangThaiCu = db.Column(db.String(50))
    TrangThaiMoi= db.Column(db.String(50))
    GhiChu      = db.Column(db.Text)          # EXTENDED: failure reason / notes
    ThoiGian    = db.Column(db.DateTime, default=datetime.utcnow)

    waybill = db.relationship("VanDon", back_populates="logs")

    def __repr__(self):
        return f"<Log {self.MaVanDon} {self.TrangThaiCu}→{self.TrangThaiMoi}>"


# ─── Table 5: GIAO_DICH ────────────────────────────────────────────────────────
class GiaoDich(db.Model):
    __tablename__ = "GIAO_DICH"

    MaGiaoDich    = db.Column(db.Integer, primary_key=True, autoincrement=True)
    MaTaiXe       = db.Column(db.Integer, db.ForeignKey("TAI_XE.MaTaiXe"), nullable=False)
    MaAdmin       = db.Column(db.Integer, db.ForeignKey("ADMIN.MaAdmin"),   nullable=False)
    SoTien        = db.Column(db.Numeric(15, 2), nullable=False)   # system-expected amount
    SoTienThucThu = db.Column(db.Numeric(15, 2))                   # EXTENDED: actual cash handed over
    ThoiGian      = db.Column(db.DateTime, default=datetime.utcnow)
    GhiChu        = db.Column(db.Text)                             # EXTENDED: notes / discrepancy

    driver = db.relationship("TaiXe",  back_populates="transactions")
    admin  = db.relationship("Admin",  back_populates="transactions")

    def __repr__(self):
        return f"<GiaoDich #{self.MaGiaoDich} TaiXe={self.MaTaiXe} {self.SoTien}₫>"


# ─── Table 6: CAU_HINH_HE_THONG (TASK 2) ───────────────────────────────────────
class CauHinhHeThong(db.Model):
    """
    Key/value store for admin-configurable system settings.
    Examples: phi_co_ban, ty_le_cod, ten_cong_ty, hotline …
    All values stored as strings; the application layer converts to the right type.
    """
    __tablename__ = "CAU_HINH_HE_THONG"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key         = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value       = db.Column(db.String(500), nullable=False, default="")
    description = db.Column(db.String(255))
    data_type   = db.Column(db.String(20), default="string")   # string | number | boolean
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CauHinh {self.key}={self.value}>"
