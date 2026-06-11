// Local Hotfix - remove leaked debug text and force 4-button technician bottom nav
(function () {
  "use strict";

  function isTechPage() {
    return /\/tech(\/|$)/.test(window.location.pathname);
  }

  function removeVisibleDebugText() {
    var badPhrases = [
      "Sidebar + datepicker initialization handled globally",
      "phase_c2_datetime_local_v2.js loaded from base.html",
      "<<<<<<<",
      ">>>>>>>",
      "201de6d603fb1b4f204c9ededc3bbd8afae02f4a"
    ];

    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) {
      var node = walker.currentNode;
      var text = node.nodeValue || "";
      if (badPhrases.some(function (p) { return text.indexOf(p) !== -1; })) {
        nodes.push(node);
      }
    }

    nodes.forEach(function (node) {
      var parent = node.parentElement;
      if (parent && parent.childNodes.length <= 3) {
        parent.remove();
      } else {
        node.nodeValue = "";
      }
    });
  }

  function hideOldTechBottomNav() {
    var candidates = document.querySelectorAll("nav, div, footer");
    candidates.forEach(function (el) {
      if (el.dataset && el.dataset.rastiTechNav === "1") return;

      var style = window.getComputedStyle(el);
      var text = (el.textContent || "").trim();

      var isBottom =
        (style.position === "fixed" || style.position === "sticky") &&
        (style.bottom === "0px" || parseInt(style.bottom || "999", 10) <= 40);

      var looksTechNav =
        text.indexOf("داشبورد") !== -1 &&
        text.indexOf("سفارش") !== -1 &&
        (text.indexOf("فاکتور") !== -1 || text.indexOf("فاکتورها") !== -1);

      if (isBottom && looksTechNav) {
        el.style.setProperty("display", "none", "important");
      }
    });
  }

  function makeLink(href, icon, label, activeTest) {
    var a = document.createElement("a");
    a.href = href;
    if (activeTest()) a.className = "is-active";
    a.innerHTML = '<span class="rasti-tech-nav-icon">' + icon + '</span><span>' + label + '</span>';
    return a;
  }

  function ensureTechBottomNav() {
    if (!isTechPage()) return;

    document.body.classList.add("rasti-tech-page");
    hideOldTechBottomNav();

    var old = document.querySelector(".rasti-tech-bottom-nav[data-rasti-tech-nav='1']");
    if (old) old.remove();

    var path = window.location.pathname;
    var nav = document.createElement("nav");
    nav.className = "rasti-tech-bottom-nav";
    nav.setAttribute("data-rasti-tech-nav", "1");
    nav.setAttribute("aria-label", "ناوبری تکنسین");

    var parts = path.split("/").filter(Boolean);
    var code = parts.length ? parts[0] : "n54";
    var techRoot = "/" + code + "/tech/";

    nav.appendChild(makeLink(techRoot, "⌂", "داشبورد", function () {
      return path === techRoot || path === techRoot.slice(0, -1);
    }));

    nav.appendChild(makeLink(techRoot + "orders/available/", "+", "سفارش جدید", function () {
      return path.indexOf("/tech/orders/available") !== -1;
    }));

    nav.appendChild(makeLink(techRoot + "orders/my/", "▣", "سفارش‌های من", function () {
      return path.indexOf("/tech/orders/") !== -1 && path.indexOf("/available") === -1;
    }));

    nav.appendChild(makeLink(techRoot + "invoices/", "◫", "فاکتورها", function () {
      return path.indexOf("/tech/invoices") !== -1;
    }));

    document.body.appendChild(nav);
  }

  function boot() {
    removeVisibleDebugText();
    ensureTechBottomNav();
  }

  document.addEventListener("DOMContentLoaded", boot);
  window.addEventListener("pageshow", boot);
  setTimeout(boot, 200);
  setTimeout(boot, 800);
})();
