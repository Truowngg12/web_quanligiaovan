/* ═══════════════════════════════════════════════════════════════
   VanDon System v2 — dashboard.js
   Toast system, animations, AJAX, DataTables init, chart
   ═══════════════════════════════════════════════════════════════ */
'use strict';

/* ─── Toast System ─────────────────────────────────────────────
   Replaces all native alert() calls.
   showToast(msg, type)  type: 'success'|'danger'|'warning'|'info'
─────────────────────────────────────────────────────────────── */
function showToast(msg, type) {
  type = type || 'info';
  const icons = {
    success: 'check-circle-fill',
    danger:  'x-circle-fill',
    warning: 'exclamation-triangle-fill',
    info:    'info-circle-fill',
  };

  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }

  const el = document.createElement('div');
  el.className = `vd-toast toast-${type}`;
  el.innerHTML =
    `<span class="toast-icon"><i class="bi bi-${icons[type] || 'info-circle-fill'}"></i></span>` +
    `<span class="toast-body">${msg}</span>` +
    `<button class="toast-close" aria-label="close">×</button>`;

  container.appendChild(el);

  // Close button
  el.querySelector('.toast-close').addEventListener('click', () => dismissToast(el));
  // Click anywhere to close
  el.addEventListener('click', () => dismissToast(el));
  // Auto dismiss after 4s
  setTimeout(() => dismissToast(el), 4000);
}

function dismissToast(el) {
  if (!el.parentNode) return;
  el.classList.add('toast-exit');
  setTimeout(() => el.remove(), 300);
}

/* ─── Sidebar toggle (mobile) ──────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const toggle  = document.getElementById('sidebarToggle');

  function openSidebar()  { sidebar && sidebar.classList.add('open');    overlay && overlay.classList.add('show'); }
  function closeSidebar() { sidebar && sidebar.classList.remove('open'); overlay && overlay.classList.remove('show'); }

  toggle  && toggle.addEventListener('click', openSidebar);
  overlay && overlay.addEventListener('click', closeSidebar);

  // Flash messages → toasts
  document.querySelectorAll('.flash-zone .alert').forEach(function (al) {
    const type = al.classList.contains('alert-success') ? 'success'
               : al.classList.contains('alert-danger')  ? 'danger'
               : al.classList.contains('alert-warning') ? 'warning' : 'info';
    const text = al.innerText.replace(/×/g, '').trim();
    if (text) showToast(text, type);
    al.remove();
  });

  // DataTables (waybill list & driver list)
  if (typeof $.fn !== 'undefined' && typeof $.fn.DataTable !== 'undefined') {
    ['#waybillTable', '#driverTable', '#transactionTable'].forEach(function (sel) {
      const el = document.querySelector(sel);
      if (el) {
        $(sel).DataTable({
          language: {
            search:           'Tìm kiếm:',
            lengthMenu:       'Hiển thị _MENU_ dòng',
            info:             'Hiển thị _START_ – _END_ / _TOTAL_ bản ghi',
            infoEmpty:        'Không có dữ liệu',
            infoFiltered:     '(lọc từ _MAX_ bản ghi)',
            paginate:         { previous: '‹', next: '›' },
            zeroRecords:      'Không tìm thấy kết quả',
            emptyTable:       'Chưa có dữ liệu',
          },
          pageLength: 20,
          order: [],
          dom: "<'row mb-2'<'col-sm-6'l><'col-sm-6 d-flex justify-content-end'f>>" +
               "<'row'<'col-12'tr>>" +
               "<'row mt-2'<'col-sm-5'i><'col-sm-7 d-flex justify-content-end'p>>",
          columnDefs: [{ orderable: false, targets: -1 }],
        });
      }
    });
  }

  // Init all bound elements
  bindAssignButtons();
  bindDriverListItems();
  bindDriverDeleteButtons();
  bindFeeCalculator();
  bindFailToggle();
});

/* ─── Currency helper ──────────────────────────────────────── */
function fmtVND(amount) {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

/* ─── Dashboard Chart (Chart.js) ───────────────────────────── */
function initOrderChart(labels, successData, failedData) {
  const ctx = document.getElementById('orderChart');
  if (!ctx || typeof Chart === 'undefined') return;

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Giao thành công',
          data: successData,
          borderColor: '#16a34a',
          backgroundColor: 'rgba(22,163,74,.1)',
          fill: true, tension: 0.45,
          pointBackgroundColor: '#16a34a',
          pointBorderColor: '#fff', pointBorderWidth: 2,
          pointRadius: 4, pointHoverRadius: 7,
        },
        {
          label: 'Giao thất bại',
          data: failedData,
          borderColor: '#dc2626',
          backgroundColor: 'rgba(220,38,38,.07)',
          fill: true, tension: 0.45,
          pointBackgroundColor: '#dc2626',
          pointBorderColor: '#fff', pointBorderWidth: 2,
          pointRadius: 4, pointHoverRadius: 7,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top', align: 'end',
          labels: { usePointStyle: true, pointStyle: 'circle', font: { size: 11, weight: '600' }, padding: 16 },
        },
        tooltip: {
          mode: 'index', intersect: false,
          backgroundColor: 'rgba(15,23,42,.88)',
          titleFont: { size: 11 }, bodyFont: { size: 12 }, padding: 10,
          callbacks: { label: ctx => '  ' + ctx.dataset.label + ': ' + ctx.parsed.y + ' đơn' },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { precision: 0, font: { size: 11 }, color: '#64748b' },
          grid: { color: 'rgba(0,0,0,.04)', drawBorder: false },
        },
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 }, color: '#64748b' },
        },
      },
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
    },
  });
}

/* ─── Waybill List & Detail: driver assignment ─────────────── */
function bindAssignButtons() {
  document.querySelectorAll('.btn-assign-submit').forEach(function (btn) {
    if (btn.dataset.bound === '1') return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', async function () {
      const waybillId = btn.dataset.id;
      const container = btn.closest('tr') || btn.closest('.d-flex') || btn.closest('.card-body') || btn.parentElement;
      if (!container) { showToast('Lỗi giao diện.', 'danger'); return; }

      const select   = container.querySelector('.driver-select');
      const driverId = select ? select.value.trim() : '';
      if (!driverId) { showToast('Vui lòng chọn tài xế trước!', 'warning'); select && select.focus(); return; }

      const orig = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

      try {
        const fd = new FormData();
        fd.append('driver_id', driverId);
        const res  = await fetch('/admin/waybills/' + encodeURIComponent(waybillId) + '/assign', {
          method: 'POST', body: fd, credentials: 'same-origin',
        });
        const data = await res.json();

        if (data.ok) {
          showToast(data.msg, 'success');
          const row = btn.closest('tr');
          if (row) {
            const statusCell = row.querySelector('.status-cell');
            const driverCell = row.querySelector('.driver-cell');
            if (statusCell) statusCell.innerHTML = '<span class="sbadge sb-delivering"><span class="sbadge-dot"></span>Đang đi giao</span>';
            if (driverCell) driverCell.innerHTML =
              '<div class="d-flex align-items-center gap-1">' +
              '<i class="bi bi-person-fill text-indigo" style="font-size:.8rem;"></i>' +
              '<span class="fw-semibold">' + data.driver_name + '</span></div>';
          } else {
            setTimeout(() => location.reload(), 1200);
          }
        } else {
          showToast(data.msg || 'Lỗi điều phối!', 'danger');
          btn.disabled = false; btn.innerHTML = orig;
        }
      } catch (e) {
        showToast('Lỗi kết nối máy chủ.', 'danger');
        btn.disabled = false; btn.innerHTML = orig;
      }
    });
  });
}

/* ─── Driver delete (AJAX + confirm modal) ─────────────────── */
function bindDriverDeleteButtons() {
  document.querySelectorAll('.btn-delete-driver').forEach(function (btn) {
    if (btn.dataset.bound === '1') return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', async function () {
      const driverId   = btn.dataset.id;
      const driverName = btn.dataset.name;

      // Custom confirm
      const confirmed = await showConfirm(
        'Xóa tài xế',
        `Bạn có chắc chắn muốn xóa tài xế <strong>${driverName}</strong>?<br>Hành động này không thể hoàn tác.`,
        'Xóa', 'danger'
      );
      if (!confirmed) return;

      const orig = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

      try {
        const res  = await fetch('/admin/drivers/' + driverId + '/delete', {
          method: 'POST', credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.ok) {
          showToast(data.msg, 'success');
          // Remove row from table
          const row = btn.closest('tr');
          if (row) {
            row.style.transition = 'opacity .3s,transform .3s';
            row.style.opacity    = '0';
            row.style.transform  = 'translateX(20px)';
            setTimeout(() => row.remove(), 320);
          }
        } else {
          showToast(data.msg, 'danger');
          btn.disabled = false; btn.innerHTML = orig;
        }
      } catch (e) {
        showToast('Lỗi kết nối.', 'danger');
        btn.disabled = false; btn.innerHTML = orig;
      }
    });
  });
}

/* ─── Confirm dialog (Bootstrap Modal, no native confirm()) ── */
function showConfirm(title, body, actionLabel, actionType) {
  return new Promise(function (resolve) {
    let modal = document.getElementById('vdConfirmModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'vdConfirmModal';
      modal.className = 'modal fade';
      modal.setAttribute('tabindex', '-1');
      modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered" style="max-width:400px;">
          <div class="modal-content" style="border-radius:16px;border:none;box-shadow:0 20px 50px rgba(0,0,0,.2);">
            <div class="modal-header border-0 pb-0">
              <h6 class="modal-title fw-bold" id="vdConfirmTitle"></h6>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body pt-2 pb-3" id="vdConfirmBody" style="font-size:.875rem;color:#475569;"></div>
            <div class="modal-footer border-0 pt-0 gap-2">
              <button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Huỷ</button>
              <button type="button" class="btn btn-sm" id="vdConfirmBtn"></button>
            </div>
          </div>
        </div>`;
      document.body.appendChild(modal);
    }

    modal.querySelector('#vdConfirmTitle').textContent  = title;
    modal.querySelector('#vdConfirmBody').innerHTML     = body;
    const confirmBtn = modal.querySelector('#vdConfirmBtn');
    confirmBtn.textContent = actionLabel || 'Xác nhận';
    confirmBtn.className = `btn btn-sm btn-${actionType || 'primary'}`;

    const bsModal = new bootstrap.Modal(modal, { backdrop: 'static' });
    bsModal.show();

    let answered = false;
    confirmBtn.onclick = function () { answered = true; bsModal.hide(); resolve(true); };
    modal.addEventListener('hidden.bs.modal', function handler() {
      modal.removeEventListener('hidden.bs.modal', handler);
      if (!answered) resolve(false);
    }, { once: true });
  });
}

/* ─── Reconciliation: AJAX driver info panel ───────────────── */
function bindDriverListItems() {
  document.querySelectorAll('.driver-list-item').forEach(function (item) {
    item.addEventListener('click', async function () {
      document.querySelectorAll('.driver-list-item').forEach(el => el.classList.remove('selected'));
      item.classList.add('selected');

      const driverId = item.dataset.driverId;
      const panel    = document.getElementById('settlePanel');
      if (!panel) return;

      panel.classList.remove('loaded');
      panel.innerHTML =
        '<div class="text-center text-muted py-4">' +
        '<div class="spinner-border spinner-border-sm text-indigo mb-2"></div>' +
        '<p class="mb-0" style="font-size:.82rem;">Đang tải…</p></div>';

      try {
        const res  = await fetch('/admin/reconciliation/' + driverId + '/info');
        const data = await res.json();
        renderSettlePanel(data);
      } catch (e) {
        panel.innerHTML = '<p class="text-danger text-center mb-0 py-3">Lỗi tải dữ liệu.</p>';
      }
    });
  });
}

function renderSettlePanel(d) {
  const panel = document.getElementById('settlePanel');
  if (!panel) return;
  panel.classList.add('loaded');

  const wbRows = (d.waybills || []).map(w =>
    `<tr>
      <td class="font-mono" style="font-size:.74rem;">${w.id}</td>
      <td style="font-size:.81rem;">${w.info}</td>
      <td class="text-end fw-bold" style="font-size:.81rem;color:#dc2626;">${fmtVND(w.cod)}</td>
    </tr>`
  ).join('');

  const noWaybills = d.van_don_count === 0;

  panel.innerHTML = `
    <div class="mb-3 p-3 rounded-3" style="background:#f8fafc;border:1px solid #e2e8f0;">
      <div class="row g-3">
        <div class="col-6">
          <div style="font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.07em;font-weight:700;">Tài xế</div>
          <div style="font-size:.95rem;font-weight:700;color:#0f172a;margin-top:.2rem;">${d.driver_name}</div>
          <div style="font-size:.75rem;color:#64748b;">${d.khu_vuc}</div>
        </div>
        <div class="col-6 text-end">
          <div style="font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.07em;font-weight:700;">COD đang giữ</div>
          <div style="font-size:1.4rem;font-weight:800;color:#dc2626;margin-top:.2rem;">${fmtVND(d.so_du_vi)}</div>
          <div style="font-size:.72rem;color:#64748b;">${d.van_don_count} vận đơn</div>
        </div>
      </div>
    </div>
    ${d.waybills && d.waybills.length > 0 ? `
    <div class="mb-3" style="max-height:180px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:8px;">
      <table class="table table-sm mb-0">
        <thead><tr>
          <th style="font-size:.67rem;padding:.5rem .75rem;">Mã VĐ</th>
          <th style="font-size:.67rem;padding:.5rem .75rem;">Người nhận</th>
          <th class="text-end" style="font-size:.67rem;padding:.5rem .75rem;">COD</th>
        </tr></thead>
        <tbody>${wbRows}</tbody>
      </table>
    </div>` : '<p class="text-muted text-center py-2 mb-3" style="font-size:.82rem;">Không có vận đơn cần đối soát.</p>'}
    <form method="POST" action="/admin/reconciliation/${d.driver_id}/confirm">
      <div class="mb-2">
        <label class="form-label">Số tiền thực thu (₫)</label>
        <input type="number" name="so_tien_thuc_thu" class="form-control"
               value="${d.so_du_vi}" required min="0" step="1000"
               style="font-size:1.05rem;font-weight:700;">
        <div style="font-size:.72rem;color:#64748b;margin-top:.3rem;">Hệ thống kỳ vọng: ${fmtVND(d.so_du_vi)}</div>
      </div>
      <div class="mb-3">
        <label class="form-label">Ghi chú (tuỳ chọn)</label>
        <input type="text" name="ghi_chu" class="form-control" placeholder="Ghi chú chênh lệch nếu có…">
      </div>
      <button type="submit" class="btn btn-primary w-100" ${noWaybills ? 'disabled' : ''}>
        <i class="bi bi-shield-check me-2"></i>Xác nhận đối soát
      </button>
    </form>`;
}

/* ─── Shipping fee calculator ──────────────────────────────── */
function bindFeeCalculator() {
  const codInput  = document.getElementById('tienCOD');
  const feeOutput = document.getElementById('feePreview');
  if (!codInput || !feeOutput) return;
  const recalc = () => {
    const cod = parseFloat(codInput.value) || 0;
    feeOutput.textContent = fmtVND(Math.max(20000, 20000 + cod * 0.01));
  };
  codInput.addEventListener('input', recalc);
  recalc();
}

/* ─── Driver update: toggle fail reason box ────────────────── */
function bindFailToggle() {
  const failBtn = document.getElementById('btnFail');
  const failBox = document.getElementById('failReasonBox');
  const okBtn   = document.getElementById('btnOk');
  const cancelBtn = document.getElementById('cancelFail');

  if (failBtn && failBox) {
    failBtn.addEventListener('click', function () {
      failBox.style.display = 'block';
      failBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      if (okBtn) okBtn.style.opacity = '0.4';
    });
  }
  if (cancelBtn) {
    cancelBtn.addEventListener('click', function () {
      if (failBox) failBox.style.display = 'none';
      if (okBtn) okBtn.style.opacity = '1';
    });
  }
  if (okBtn) {
    okBtn.addEventListener('click', async function () {
      const confirmed = await showConfirm(
        'Xác nhận giao thành công',
        'Bạn xác nhận đã giao hàng và thu tiền COD thành công?<br><small class="text-muted">Ví COD sẽ được cộng tiền ngay lập tức.</small>',
        'Xác nhận', 'success'
      );
      if (confirmed) document.getElementById('formSuccess').submit();
    });
  }
}
