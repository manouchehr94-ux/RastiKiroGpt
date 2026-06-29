/* Communication Settings — matrix role toggles + toast
   Generic utilities (digit normaliser, amount formatter) live in rasti_ui_formatters.js */
(function () {
    'use strict';

    /* ─── Toast ─── */
    var toast = null;
    var toastTimer = null;

    function getToast() {
        if (!toast) toast = document.getElementById('comm-toast');
        return toast;
    }

    function showToast(msg, isError) {
        var el = getToast();
        if (!el) return;
        el.textContent = msg;
        el.style.background = isError ? 'var(--color-danger-dark)' : 'var(--color-slate-800)';
        el.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { el.classList.remove('show'); }, 2800);
    }

    /* ─── Matrix role toggle (delegated click) ─── */
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('button.comm-role-toggle[data-event-key]');
        if (!btn) return;
        if (btn.classList.contains('saving')) return;

        var sw = btn.querySelector('.toggle-sw');
        if (!sw) return;

        var eventKey = btn.dataset.eventKey;
        var field = btn.dataset.field;
        var wasOn = sw.classList.contains('on');

        /* Optimistic update + double-click lock */
        btn.classList.add('saving');
        wasOn ? sw.classList.remove('on') : sw.classList.add('on');

        var csrfEl = document.getElementById('comm-csrf');
        var body = new URLSearchParams();
        body.append('csrfmiddlewaretoken', csrfEl ? csrfEl.value : '');
        body.append('event_key', eventKey);
        body.append('field', field);
        body.append('value', wasOn ? '0' : '1');

        fetch(window.location.pathname, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: body.toString(),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            btn.classList.remove('saving');
            if (data.ok) {
                var isOn = data.new_value;
                isOn ? sw.classList.add('on') : sw.classList.remove('on');
                showToast(data.message || (isOn ? 'فعال شد' : 'غیرفعال شد'), false);
            } else {
                /* Revert to original state on server error */
                wasOn ? sw.classList.add('on') : sw.classList.remove('on');
                showToast(data.message || 'خطا در ذخیره', true);
            }
        })
        .catch(function () {
            btn.classList.remove('saving');
            wasOn ? sw.classList.add('on') : sw.classList.remove('on');
            showToast('خطا در اتصال به سرور', true);
        });
    });
})();
