// Phase B V2 - Mobile Right Sidebar Fix
// Strong runtime controller for existing duplicated sidebar system.
(function () {
  'use strict';

  var MOBILE_WIDTH = 1024;

  function isMobile() {
    return window.innerWidth < MOBILE_WIDTH;
  }

  function getSidebar() {
    return document.getElementById('sidebar') ||
           document.querySelector('#app aside') ||
           document.querySelector('.admin-sidebar') ||
           document.querySelector('.sidebar');
  }

  function getOverlay() {
    return document.getElementById('sidebarOverlay') ||
           document.querySelector('.sidebar-overlay');
  }

  function important(el, prop, value) {
    if (el && el.style && el.style.setProperty) {
      el.style.setProperty(prop, value, 'important');
    }
  }

  function resetInline(el, props) {
    if (!el || !el.style) return;
    props.forEach(function (p) {
      el.style.removeProperty(p);
    });
  }

  function forceSidebarOpen(sidebar) {
    sidebar.classList.add('open', 'sidebar-opened', 'is-open');
    sidebar.classList.remove('translate-x-full', '-translate-x-full', 'hidden');

    important(sidebar, 'display', 'flex');
    important(sidebar, 'position', 'fixed');
    important(sidebar, 'top', '0');
    important(sidebar, 'right', '0');
    important(sidebar, 'bottom', '0');
    important(sidebar, 'left', 'auto');
    important(sidebar, 'width', 'min(18rem, 86vw)');
    important(sidebar, 'max-width', '86vw');
    important(sidebar, 'height', '100vh');
    important(sidebar, 'max-height', '100vh');
    important(sidebar, 'overflow-y', 'auto');
    important(sidebar, 'z-index', '2147483647');
    important(sidebar, 'transform', 'translateX(0)');
    important(sidebar, 'visibility', 'visible');
    important(sidebar, 'opacity', '1');
    important(sidebar, 'pointer-events', 'auto');

    sidebar.setAttribute('aria-hidden', 'false');
  }

  function forceSidebarClosed(sidebar) {
    sidebar.classList.remove('open', 'sidebar-opened', 'is-open');
    sidebar.classList.add('translate-x-full');

    important(sidebar, 'display', 'flex');
    important(sidebar, 'position', 'fixed');
    important(sidebar, 'top', '0');
    important(sidebar, 'right', '0');
    important(sidebar, 'bottom', '0');
    important(sidebar, 'left', 'auto');
    important(sidebar, 'width', 'min(18rem, 86vw)');
    important(sidebar, 'max-width', '86vw');
    important(sidebar, 'height', '100vh');
    important(sidebar, 'z-index', '2147483647');
    important(sidebar, 'transform', 'translateX(110%)');
    important(sidebar, 'visibility', 'hidden');
    important(sidebar, 'opacity', '0');
    important(sidebar, 'pointer-events', 'none');

    sidebar.setAttribute('aria-hidden', 'true');
  }

  function forceDesktop(sidebar, overlay) {
    sidebar.classList.add('open', 'sidebar-opened');
    sidebar.classList.remove('translate-x-full', '-translate-x-full', 'hidden');
    sidebar.setAttribute('aria-hidden', 'false');

    resetInline(sidebar, [
      'display','position','top','right','bottom','left','width','max-width',
      'height','max-height','overflow-y','z-index','transform','visibility',
      'opacity','pointer-events'
    ]);

    if (overlay) {
      overlay.classList.remove('active', 'open');
      overlay.classList.add('hidden');
      resetInline(overlay, ['display','visibility','opacity','pointer-events','z-index']);
    }

    document.body.classList.remove('rasti-sidebar-open', 'admin-sidebar-is-open', 'no-scroll');
    document.body.style.removeProperty('overflow');
  }

  function forceOverlayOpen(overlay) {
    if (!overlay) return;
    overlay.classList.add('active', 'open');
    overlay.classList.remove('hidden');

    important(overlay, 'display', 'block');
    important(overlay, 'position', 'fixed');
    important(overlay, 'inset', '0');
    important(overlay, 'z-index', '2147483646');
    important(overlay, 'background', 'rgba(15, 23, 42, 0.45)');
    important(overlay, 'backdrop-filter', 'none');
    important(overlay, 'visibility', 'visible');
    important(overlay, 'opacity', '1');
    important(overlay, 'pointer-events', 'auto');
  }

  function forceOverlayClosed(overlay) {
    if (!overlay) return;
    overlay.classList.remove('active', 'open');
    overlay.classList.add('hidden');

    important(overlay, 'display', 'none');
    important(overlay, 'visibility', 'hidden');
    important(overlay, 'opacity', '0');
    important(overlay, 'pointer-events', 'none');
  }

  function openSidebar() {
    var sidebar = getSidebar();
    var overlay = getOverlay();
    if (!sidebar) return;

    if (!isMobile()) {
      forceDesktop(sidebar, overlay);
      return;
    }

    forceSidebarOpen(sidebar);
    forceOverlayOpen(overlay);

    document.body.classList.add('rasti-sidebar-open', 'admin-sidebar-is-open', 'no-scroll');
    important(document.body, 'overflow', 'hidden');
  }

  function closeSidebar() {
    var sidebar = getSidebar();
    var overlay = getOverlay();
    if (!sidebar) return;

    if (!isMobile()) {
      forceDesktop(sidebar, overlay);
      return;
    }

    forceSidebarClosed(sidebar);
    forceOverlayClosed(overlay);

    document.body.classList.remove('rasti-sidebar-open', 'admin-sidebar-is-open', 'no-scroll');
    document.body.style.removeProperty('overflow');
  }

  function toggleSidebar() {
    var sidebar = getSidebar();
    if (!sidebar) return;

    var opened = sidebar.classList.contains('open') ||
                 sidebar.classList.contains('sidebar-opened') ||
                 document.body.classList.contains('rasti-sidebar-open') ||
                 document.body.classList.contains('admin-sidebar-is-open');

    if (isMobile() && opened) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  window.openSidebar = openSidebar;
  window.closeSidebar = closeSidebar;
  window.toggleSidebar = toggleSidebar;

  function boot() {
    var sidebar = getSidebar();
    var overlay = getOverlay();
    if (!sidebar) return;

    if (isMobile()) {
      closeSidebar();
    } else {
      forceDesktop(sidebar, overlay);
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
  window.addEventListener('pageshow', boot);
  window.addEventListener('resize', boot);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSidebar();
  });

  document.addEventListener('click', function (e) {
    var overlay = getOverlay();
    if (overlay && e.target === overlay) {
      closeSidebar();
    }
  }, true);
})();
