// Phase C2 V2 - Force attach Jalali DatePicker to datetime-local/text date fields.
(function () {
  "use strict";

  function forcePrepare(input) {
    if (!input) return;

    if (input.type === "datetime-local" || input.type === "date") {
      input.dataset.originalType = input.type;
      try { input.type = "text"; } catch (e) {}
    }

    input.classList.add("jalali-date-input");
    input.setAttribute("data-jalali-datepicker", "1");
    input.setAttribute("autocomplete", "off");
    input.setAttribute("inputmode", "numeric");

    if (!input.placeholder || input.placeholder.indexOf("mm/") >= 0) {
      input.placeholder = "مثلاً 1404/12/01";
    }

    // Important: previous Phase C may mark dataset.jdpAttached before real click binding.
    // Reset it, then call the main datepicker initializer.
    delete input.dataset.jdpAttached;

    if (window.initJalaliDatepicker) {
      window.initJalaliDatepicker(input);
    }

    if (window.RastiJalaliDatepicker && window.RastiJalaliDatepicker.attach) {
      window.RastiJalaliDatepicker.attach(input);
    }
  }

  function scan() {
    var selectors = [
      'input[type="datetime-local"]',
      'input[type="date"]',
      'input[name*="started" i]',
      'input[name*="expires" i]',
      'input[name*="start" i]',
      'input[name*="expire" i]',
      'input[name*="date" i]'
    ].join(',');

    document.querySelectorAll(selectors).forEach(forcePrepare);
  }

  function boot() {
    scan();

    setTimeout(scan, 250);
    setTimeout(scan, 800);
    setTimeout(scan, 1500);
  }

  document.addEventListener("DOMContentLoaded", boot);
  window.addEventListener("pageshow", boot);

  if (window.MutationObserver) {
    document.addEventListener("DOMContentLoaded", function () {
      var timer = null;
      var observer = new MutationObserver(function () {
        clearTimeout(timer);
        timer = setTimeout(scan, 150);
      });
      observer.observe(document.body, { childList: true, subtree: true });
    });
  }
})();
