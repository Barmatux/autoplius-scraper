(function () {
  const MOBILE_MQL = window.matchMedia("(max-width: 768px)");

  function isMobileViewport() {
    return MOBILE_MQL.matches;
  }

  function setOpen(panel, open) {
    panel.classList.toggle("is-open", open);
    const toggle = panel.querySelector("[data-filters-toggle]");
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    }
  }

  function initPanel(panel) {
    const toggle = panel.querySelector("[data-filters-toggle]");
    if (!toggle) {
      return;
    }

    function syncForViewport() {
      if (!isMobileViewport()) {
        setOpen(panel, true);
        return;
      }
      if (!panel.dataset.initialized) {
        panel.dataset.initialized = "1";
        const hasBadge = Boolean(panel.querySelector("[data-filters-badge]"));
        setOpen(panel, panel.classList.contains("is-open") || hasBadge);
        return;
      }
      if (!panel.classList.contains("is-open")) {
        setOpen(panel, false);
      }
    }

    toggle.addEventListener("click", () => {
      if (!isMobileViewport()) {
        return;
      }
      setOpen(panel, !panel.classList.contains("is-open"));
    });

    if (typeof MOBILE_MQL.addEventListener === "function") {
      MOBILE_MQL.addEventListener("change", syncForViewport);
    } else {
      MOBILE_MQL.addListener(syncForViewport);
    }

    syncForViewport();
  }

  document.querySelectorAll("[data-filters-panel]").forEach(initPanel);
})();
