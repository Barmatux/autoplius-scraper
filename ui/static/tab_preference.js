(function () {
  const STORAGE_KEY = "listings-return-v1";
  const LIST_PATHS = new Set(["/", "/catalog", "/analytics"]);

  function saveReturnTarget(url) {
    try {
      const target = url || window.location.pathname + window.location.search;
      if (!target.startsWith("/") || target.startsWith("//")) {
        return;
      }
      const path = target.split("?", 1)[0];
      if (LIST_PATHS.has(path)) {
        localStorage.setItem(STORAGE_KEY, target);
      }
    } catch (_err) {
      /* ignore */
    }
  }

  function readReturnTarget() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && saved.startsWith("/") && !saved.startsWith("//")) {
        return saved;
      }
    } catch (_err) {
      /* ignore */
    }
    return null;
  }

  saveReturnTarget();

  document.querySelectorAll(".tabs .tab").forEach((link) => {
    link.addEventListener("click", () => {
      saveReturnTarget(link.href);
    });
  });

  document.querySelectorAll("[data-save-return]").forEach((link) => {
    link.addEventListener("click", () => {
      saveReturnTarget();
    });
  });

  const backLink = document.querySelector("[data-back-to-list]");
  if (backLink) {
    const href = backLink.getAttribute("href") || "";
    if (href === "/" || href.startsWith("/?")) {
      const saved = readReturnTarget();
      if (saved) {
        backLink.setAttribute("href", saved);
      }
    }
  }
})();
