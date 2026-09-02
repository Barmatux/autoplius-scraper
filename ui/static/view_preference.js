(function () {
  const STORAGE_KEY = "listings-view-v1";
  const MOBILE_MQL = window.matchMedia("(max-width: 768px)");
  const url = new URL(window.location.href);

  function isMobileViewport() {
    return MOBILE_MQL.matches;
  }

  function ensureCardsView() {
    if (url.searchParams.get("view") === "cards") {
      return false;
    }
    url.searchParams.set("view", "cards");
    window.location.replace(url.toString());
    return true;
  }

  if (!url.searchParams.has("view")) {
    if (isMobileViewport()) {
      ensureCardsView();
      return;
    }
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "cards") {
        url.searchParams.set("view", "cards");
        window.location.replace(url.toString());
        return;
      }
    } catch (_err) {
      /* ignore */
    }
  } else if (isMobileViewport() && url.searchParams.get("view") !== "cards") {
    ensureCardsView();
    return;
  }

  const current = url.searchParams.get("view") === "cards" ? "cards" : "table";

  document.querySelectorAll("[data-listings-view-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-listings-view-btn");
      if (!view || view === current) {
        return;
      }
      if (isMobileViewport() && view === "table") {
        return;
      }
      try {
        localStorage.setItem(STORAGE_KEY, view);
      } catch (_err) {
        /* ignore */
      }
      const next = new URL(window.location.href);
      if (view === "cards") {
        next.searchParams.set("view", "cards");
      } else {
        next.searchParams.delete("view");
      }
      window.location.href = next.toString();
    });
  });
})();
