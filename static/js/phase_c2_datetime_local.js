// Phase C2 - Jalali DatePicker for datetime-local fields (Subscriptions + similar)
// Converts all input[type=datetime-local] to input[type=text] and attaches Jalali DatePicker
(function() {
  "use strict";

  function attachToDatetimeLocal(input) {
    if (!input || input.dataset.jdpAttached) return;
    input.dataset.jdpAttached = "1";
    if (input.type === "datetime-local") {
      input.dataset.originalType = input.type;
      try { input.type = "text"; } catch(e){}
    }
    input.classList.add("jalali-date-input");
    input.setAttribute("data-jalali-datepicker", "1");
    input.setAttribute("autocomplete", "off");
    input.setAttribute("inputmode", "numeric");
    if(!input.placeholder) input.placeholder = "مثلاً 1404/12/01";
    input.addEventListener("focus", function(){ if(window.RastiJalaliDatepicker) window.RastiJalaliDatepicker.attach(input); });
  }

  function attachAll(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('input[type="datetime-local"]').forEach(attachToDatetimeLocal);
    if(scope.matches && scope.matches('input[type="datetime-local"]')) attachToDatetimeLocal(scope);
  }

  function observeMutations() {
    if(!window.MutationObserver) return;
    const observer = new MutationObserver(function(muts){
      let shouldAttach = false;
      for(const m of muts) if(m.addedNodes && m.addedNodes.length){ shouldAttach = true; break; }
      if(!shouldAttach) return;
      window.clearTimeout(window._jalaliMutationTimer);
      window._jalaliMutationTimer = window.setTimeout(function(){ attachAll(document); }, 100);
    });
    observer.observe(document.body, {childList:true, subtree:true});
  }

  function boot() {
    attachAll(document);
    observeMutations();
  }

  document.addEventListener("DOMContentLoaded", boot);
  window.addEventListener("pageshow", boot);
})();
