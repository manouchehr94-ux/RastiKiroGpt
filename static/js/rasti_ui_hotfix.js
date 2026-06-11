
(function () {
  'use strict';
  var SCROLL_KEY = 'rasti_sidebar_scroll';
  var COLLAPSED_KEY = 'rasti_sidebar_collapsed';
  function qs(sel) { return document.querySelector(sel); }
  function getSidebar() { return document.getElementById('sidebar') || qs('.sidebar') || qs('.admin-sidebar'); }
  function getOverlay() { return document.getElementById('sidebarOverlay') || qs('.sidebar-overlay'); }
  function isMobile() { return window.innerWidth < 1024; }
  function setOverlayVisible(visible) {
    var overlay = getOverlay(); if (!overlay) return;
    if (visible && isMobile()) { overlay.classList.add('active'); overlay.classList.remove('hidden'); overlay.style.display = 'block'; overlay.style.opacity = '1'; overlay.style.visibility = 'visible'; overlay.style.pointerEvents = 'auto'; }
    else { overlay.classList.remove('active'); overlay.classList.add('hidden'); overlay.style.display = 'none'; overlay.style.opacity = '0'; overlay.style.visibility = 'hidden'; overlay.style.pointerEvents = 'none'; }
  }
  function setSidebarVisible(visible) {
    var sidebar = getSidebar(); if (!sidebar) return;
    if (visible || !isMobile()) { sidebar.classList.add('open'); sidebar.classList.add('sidebar-opened'); sidebar.classList.add('is-open'); sidebar.classList.remove('translate-x-full'); sidebar.classList.remove('-translate-x-full'); sidebar.style.transform = 'translateX(0)'; sidebar.style.visibility = 'visible'; sidebar.style.opacity = '1'; sidebar.style.pointerEvents = 'auto'; sidebar.setAttribute('aria-hidden','false'); }
    else { sidebar.classList.remove('open'); sidebar.classList.remove('sidebar-opened'); sidebar.classList.remove('is-open'); sidebar.classList.add('translate-x-full'); sidebar.style.transform = 'translateX(110%)'; sidebar.style.visibility = 'hidden'; sidebar.style.opacity = '0'; sidebar.style.pointerEvents = 'none'; sidebar.setAttribute('aria-hidden','true'); }
  }
  window.openSidebar = function openSidebar() { setSidebarVisible(true); setOverlayVisible(true); document.body.classList.add('rasti-sidebar-open'); document.body.classList.add('admin-sidebar-is-open'); if (isMobile()) document.body.style.overflow = 'hidden'; try { localStorage.setItem(COLLAPSED_KEY,'false'); } catch(e){} };
  window.closeSidebar = function closeSidebar() { if (isMobile()) setSidebarVisible(false); else setSidebarVisible(true); setOverlayVisible(false); document.body.classList.remove('rasti-sidebar-open'); document.body.classList.remove('admin-sidebar-is-open'); document.body.style.overflow = ''; try { localStorage.setItem(COLLAPSED_KEY, isMobile() ? 'true' : 'false'); } catch(e){} };
  window.toggleSidebar = function toggleSidebar() { var sidebar = getSidebar(); var open = !!(sidebar && (sidebar.classList.contains('open') || sidebar.classList.contains('sidebar-opened') || sidebar.classList.contains('is-open')) && isMobile()); if (open) window.closeSidebar(); else window.openSidebar(); };
  function restoreSidebarScroll() { var sidebar = getSidebar(); if (!sidebar) return; try { var saved = sessionStorage.getItem(SCROLL_KEY); if (saved !== null) sidebar.scrollTop = parseInt(saved, 10) || 0; sidebar.addEventListener('scroll', function(){ sessionStorage.setItem(SCROLL_KEY, String(sidebar.scrollTop || 0)); }, {passive:true}); if (localStorage.getItem(COLLAPSED_KEY) === null) localStorage.setItem(COLLAPSED_KEY, isMobile() ? 'true' : 'false'); } catch(e){} }
  function initDateInputs() { var selector = ['input[type="date"]','input.jalali-date-input','[data-jalali-datepicker]','input[name*="date" i]','input[name*="_from" i]','input[name*="_to" i]','input[name="from"]','input[name="to"]','input[name="start"]','input[name="end"]'].join(','); document.querySelectorAll(selector).forEach(function(el){ el.classList.add('jalali-date-input'); el.setAttribute('data-jalali-datepicker','1'); if (typeof window.initJalaliDatepicker === 'function') { try { window.initJalaliDatepicker(el); } catch(e){} } if (window.RastiJalaliDatepicker && typeof window.RastiJalaliDatepicker.attach === 'function') { try { window.RastiJalaliDatepicker.attach(); } catch(e){} } }); }
  function formatNumbers() { if (window.RastiFormatNumbers && typeof window.RastiFormatNumbers.apply === 'function') { try { window.RastiFormatNumbers.apply(); return; } catch(e){} } var selectors = '.stat-value,.text-2xl,.fin-number,[data-format-number],td,th'; document.querySelectorAll(selectors).forEach(function(el){ if (!el || el.children.length) return; var txt = (el.textContent || '').trim(); if (!/^[-+]?\d{4,}$/.test(txt)) return; if (/^09\d+/.test(txt)) return; el.textContent = txt.replace(/\B(?=(\d{3})+(?!\d))/g, ','); }); }
  function boot() { restoreSidebarScroll(); initDateInputs(); formatNumbers(); window.closeSidebar(); }
  document.addEventListener('DOMContentLoaded', boot); window.addEventListener('pageshow', boot); window.addEventListener('resize', function(){ window.closeSidebar(); }); document.addEventListener('keydown', function(e){ if (e.key === 'Escape') window.closeSidebar(); }); document.addEventListener('click', function(e){ var overlay = getOverlay(); if (overlay && e.target === overlay) window.closeSidebar(); }); setTimeout(boot,0); setTimeout(function(){ if (!document.body.classList.contains('rasti-sidebar-open')) window.closeSidebar(); },150);
})();
