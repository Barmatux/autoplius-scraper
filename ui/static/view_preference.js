(function () {
  const STORAGE_KEY = "listings-view-v1";
  const MOBILE_MAX = 700;
  const url = new URL(window.location.href);
  const isMobile = window.matchMedia(`(max-width: ${MOBILE_MAX}px)`).matches;

  if (!url.searchParams.has("view")) {
    try {
      if (isMobile) {
        url.searchParams.set("view", "cards");
        window.location.replace(url.toString());
        return;
      }
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "cards") {
        url.searchParams.set("view", "cards");
        window.location.replace(url.toString());
        return;
      }
    } catch (_err) {
      /* ignore */
    }
  } else if (isMobile && url.searchParams.get("view") !== "cards") {
    url.searchParams.set("view", "cards");
    window.location.replace(url.toString());
    return;
  }

  const current = url.searchParams.get("view") === "cards" ? "cards" : "table";

  document.querySelectorAll("[data-listings-view-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-listings-view-btn");
      if (!view || view === current) {
        return;
      }
      if (isMobile && view !== "cards") {
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
