(function () {
  const STORAGE_KEY = "listings-view-v1";
  const url = new URL(window.location.href);

  if (!url.searchParams.has("view")) {
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
  }

  const current = url.searchParams.get("view") === "cards" ? "cards" : "table";

  document.querySelectorAll("[data-listings-view-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-listings-view-btn");
      if (!view || view === current) {
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
