/**
 * ═══════════════════════════════════════════════════════════════
 * VanDon Toast Notification System — Standalone Reusable Snippet
 * ═══════════════════════════════════════════════════════════════
 *
 * USAGE:
 *   showToast('Lưu thành công!', 'success')
 *   showToast('Lỗi kết nối!',   'danger')
 *   showToast('Chú ý!',         'warning')
 *   showToast('Thông báo',      'info')
 *
 * CONFIRM DIALOG (async — replaces window.confirm):
 *   const ok = await showConfirm('Xoá?', 'Hành động không thể hoàn tác.', 'Xoá', 'danger')
 *   if (ok) { ... }
 *
 * DROP-IN REPLACEMENT for native alert():
 *   Replace  alert('Thành công!')
 *   With     showToast('Thành công!', 'success')
 *
 * REQUIREMENTS: Bootstrap 5 JS + Bootstrap Icons
 * ═══════════════════════════════════════════════════════════════
 */

/* ── Required CSS (add to your stylesheet) ─────────────────────
#toastContainer {
  position: fixed;
  top: 1.125rem; right: 1.125rem;
  z-index: 9999;
  display: flex; flex-direction: column; gap: .5rem;
  pointer-events: none;
}
.vd-toast {
  pointer-events: all;
  min-width: 300px; max-width: 380px;
  padding: .875rem 1.125rem;
  border-radius: 12px;
  display: flex; align-items: flex-start; gap: .75rem;
  box-shadow: 0 10px 25px rgba(0,0,0,.15);
  color: #fff; font-size: .845rem; font-weight: 500;
  cursor: pointer; position: relative; overflow: hidden;
  animation: toast-enter .3s cubic-bezier(.34,1.56,.64,1) both;
}
.vd-toast::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
  background: rgba(255,255,255,.35);
  animation: toast-progress 4s linear forwards;
  transform-origin: left;
}
@keyframes toast-enter {
  from { opacity: 0; transform: translateX(24px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes toast-progress {
  from { transform: scaleX(1); }
  to   { transform: scaleX(0); }
}
@keyframes toast-exit {
  to { opacity: 0; transform: translateX(20px); max-height: 0; margin: 0; padding: 0; }
}
.vd-toast.toast-success { background: linear-gradient(135deg, #15803d, #16a34a); }
.vd-toast.toast-danger  { background: linear-gradient(135deg, #b91c1c, #dc2626); }
.vd-toast.toast-warning { background: linear-gradient(135deg, #b45309, #d97706); }
.vd-toast.toast-info    { background: linear-gradient(135deg, #3730a3, #4f46e5); }
.toast-exit { animation: toast-exit .25s ease forwards; }
── End required CSS ─────────────────────────────────────────── */

'use strict';

// ── showToast ────────────────────────────────────────────────
function showToast(msg, type, duration) {
  type     = type     || 'info';
  duration = duration || 4000;

  const ICONS = {
    success: 'check-circle-fill',
    danger:  'x-circle-fill',
    warning: 'exclamation-triangle-fill',
    info:    'info-circle-fill',
  };

  // Ensure container exists
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }

  // Build toast element
  const toast = document.createElement('div');
  toast.className = `vd-toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  toast.innerHTML =
    `<i class="bi bi-${ICONS[type] || 'info-circle-fill'}" style="font-size:1.1rem;flex-shrink:0;margin-top:.05rem;"></i>` +
    `<span style="flex:1;line-height:1.45;">${msg}</span>` +
    `<button onclick="dismissToast(this.parentElement)" aria-label="close"
             style="background:none;border:none;color:rgba(255,255,255,.75);font-size:1rem;line-height:1;cursor:pointer;padding:0;flex-shrink:0;">×</button>`;

  container.appendChild(toast);

  // Click anywhere to dismiss
  toast.addEventListener('click', function () { dismissToast(toast); });

  // Auto-dismiss
  const timer = setTimeout(function () { dismissToast(toast); }, duration);
  toast._timer = timer;

  return toast;
}

// ── dismissToast ────────────────────────────────────────────
function dismissToast(el) {
  if (!el || !el.parentNode) return;
  clearTimeout(el._timer);
  el.classList.add('toast-exit');
  setTimeout(function () { el && el.remove(); }, 300);
}

// ── showConfirm (replaces window.confirm) ───────────────────
function showConfirm(title, body, actionLabel, actionType) {
  return new Promise(function (resolve) {
    // Inject modal if needed
    let modal = document.getElementById('vdConfirmModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'vdConfirmModal';
      modal.className = 'modal fade';
      modal.setAttribute('tabindex', '-1');
      modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered" style="max-width:400px;">
          <div class="modal-content" style="border-radius:16px;border:none;box-shadow:0 20px 50px rgba(0,0,0,.2);">
            <div class="modal-header border-0 pb-1">
              <h6 class="modal-title fw-bold text-dark" id="vdConfirmTitle"></h6>
              <button class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body pt-1 pb-3 text-muted" id="vdConfirmBody"
                 style="font-size:.875rem;"></div>
            <div class="modal-footer border-0 pt-0 gap-2">
              <button class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Huỷ</button>
              <button class="btn btn-sm" id="vdConfirmBtn"></button>
            </div>
          </div>
        </div>`;
      document.body.appendChild(modal);
    }

    // Populate
    document.getElementById('vdConfirmTitle').textContent = title || 'Xác nhận';
    document.getElementById('vdConfirmBody').innerHTML    = body  || 'Bạn có chắc chắn?';
    const confirmBtn = document.getElementById('vdConfirmBtn');
    confirmBtn.textContent = actionLabel || 'Xác nhận';
    confirmBtn.className   = `btn btn-sm btn-${actionType || 'primary'}`;

    const bsModal = new bootstrap.Modal(modal, { backdrop: 'static' });
    bsModal.show();

    let answered = false;
    confirmBtn.onclick = function () {
      answered = true;
      bsModal.hide();
      resolve(true);
    };
    modal.addEventListener('hidden.bs.modal', function handler() {
      modal.removeEventListener('hidden.bs.modal', handler);
      if (!answered) resolve(false);
    }, { once: true });
  });
}

// ── Flash message → Toast converter ─────────────────────────
// Call once after DOM ready to convert server-rendered flash messages
function convertFlashToToasts(containerSelector) {
  const zone = document.querySelector(containerSelector || '.flash-zone');
  if (!zone) return;
  zone.querySelectorAll('.alert').forEach(function (al) {
    const type = al.classList.contains('alert-success') ? 'success'
               : al.classList.contains('alert-danger')  ? 'danger'
               : al.classList.contains('alert-warning') ? 'warning' : 'info';
    const text = al.innerText.replace(/×/g, '').trim();
    if (text) showToast(text, type);
    al.remove();
  });
}

// ── Auto-init on DOM ready ───────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  convertFlashToToasts();
});

/* ── QUICK REFERENCE ──────────────────────────────────────────
   showToast(msg, type, duration?)
     msg      : HTML or plain string
     type     : 'success' | 'danger' | 'warning' | 'info'
     duration : milliseconds (default 4000)

   showConfirm(title, body, buttonLabel, buttonType)
     Returns Promise<boolean>
     await showConfirm('Delete?', 'Cannot undo.', 'Delete', 'danger')

   convertFlashToToasts(selector?)
     Converts .flash-zone .alert elements to toasts
     selector: CSS selector of container (default '.flash-zone')
─────────────────────────────────────────────────────────────── */
