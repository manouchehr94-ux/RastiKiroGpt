
window.RastiFormatNumbers = window.RastiFormatNumbers || { apply: function () { var selector = '.stat-value,.fin-number,[data-format-number],.dashboard-content td,.dashboard-content th'; document.querySelectorAll(selector).forEach(function (el) { if (!el || el.children.length) return; var txt = (el.textContent || '').trim(); if (!/^[-+]?\d{4,}$/.test(txt)) return; if (/^09\d+/.test(txt)) return; el.textContent = txt.replace(/\B(?=(\d{3})+(?!\d))/g, ','); el.classList.add('rasti-number'); }); } };
document.addEventListener('DOMContentLoaded', function () { window.RastiFormatNumbers.apply(); });

/* Persian/Arabic digit normaliser — scans text nodes for 'تا سقف X ریال' and adds commas */
window.RastiFixPersianAmounts = window.RastiFixPersianAmounts || {
    _normalizeDigits: function (v) {
        v = (v || '').toString();
        var fa = '۰۱۲۳۴۵۶۷۸۹', ar = '٠١٢٣٤٥٦٧٨٩';
        for (var i = 0; i < 10; i++) v = v.replaceAll(fa[i], String(i)).replaceAll(ar[i], String(i));
        return v;
    },
    _comma: function (n) {
        n = this._normalizeDigits(n).replace(/[^\d]/g, '');
        return n ? n.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : n;
    },
    _fixNode: function (node) {
        var self = this, text = node.nodeValue || '';
        var next = text.replace(/تا سقف\s+([0-9۰-۹٠-٩]{4,})\s+ریال/g, function (_, num) {
            return 'تا سقف ' + self._comma(num) + ' ریال';
        });
        if (next !== text) node.nodeValue = next;
    },
    apply: function () {
        var self = this, walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(function (n) { self._fixNode(n); });
    }
};
document.addEventListener('DOMContentLoaded', function () { window.RastiFixPersianAmounts.apply(); });
