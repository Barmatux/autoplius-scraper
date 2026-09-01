(function () {
  const STORAGE_KEY = "listings-sort-v1";
  const url = new URL(window.location.href);

  if (!url.searchParams.has("sort")) {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        url.searchParams.set("sort", saved);
        window.location.replace(url.toString());
        return;
      }
    } catch (_err) {
      /* ignore */
    }
  }

  document.querySelectorAll(".sort-link").forEach((link) => {
    link.addEventListener("click", () => {
      try {
        const next = new URL(link.href);
        const sort = next.searchParams.get("sort");
        if (sort) {
          localStorage.setItem(STORAGE_KEY, sort);
        }
      } catch (_err) {
        /* ignore */
      }
    });
  });

  const form = document.querySelector("form.filters");
  const sortInput = form?.querySelector('input[name="sort"]');
  if (form && sortInput) {
    form.addEventListener("submit", () => {
      try {
        if (sortInput.value) {
          localStorage.setItem(STORAGE_KEY, sortInput.value);
        }
      } catch (_err) {
        /* ignore */
      }
    });
  }
})();
