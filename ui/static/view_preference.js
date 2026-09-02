(function () {
  const STORAGE_KEY = "listings-view-v1";
  const ROOT = document.documentElement;

  function getSavedView() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "cards" || saved === "table") {
        return saved;
      }
    } catch (_err) {
      /* ignore */
    }
    return "table";
  }

  function applyView(view) {
    const mode = view === "cards" ? "cards" : "table";
    ROOT.dataset.listingsView = mode;
    document.querySelectorAll("[data-listings-view-btn]").forEach((btn) => {
      const active = btn.getAttribute("data-listings-view-btn") === mode;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    document.querySelectorAll("[data-listings-view-panel]").forEach((panel) => {
      const show = panel.getAttribute("data-listings-view-panel") === mode;
      panel.hidden = !show;
    });
  }

  function saveView(view) {
    try {
      localStorage.setItem(STORAGE_KEY, view);
    } catch (_err) {
      /* ignore */
    }
  }

  applyView(getSavedView());

  document.querySelectorAll("[data-listings-view-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-listings-view-btn");
      if (!view) return;
      applyView(view);
      saveView(view);
    });
  });
})();
