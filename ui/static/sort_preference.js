(function () {
  const STORAGE_KEY = "listings-sort-v2";
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

  function saveSort(sort) {
    try {
      if (sort) {
        localStorage.setItem(STORAGE_KEY, sort);
      }
    } catch (_err) {
      /* ignore */
    }
  }

  document.querySelectorAll(".sort-link").forEach((link) => {
    link.addEventListener("click", () => {
      try {
        const next = new URL(link.href);
        saveSort(next.searchParams.get("sort"));
      } catch (_err) {
        /* ignore */
      }
    });
  });

  const form = document.querySelector("form.filters");
  const sortInput = form?.querySelector('input[name="sort"]');
  if (form && sortInput) {
    form.addEventListener("submit", () => {
      saveSort(sortInput.value);
    });
  }

  document.querySelectorAll("[data-cards-sort]").forEach((select) => {
    select.addEventListener("change", () => {
      const sort = select.value;
      if (!sort) {
        return;
      }
      saveSort(sort);
      const next = new URL(window.location.href);
      next.searchParams.set("sort", sort);
      next.searchParams.set("page", "1");
      if (sortInput) {
        sortInput.value = sort;
      }
      window.location.href = next.toString();
    });
  });
})();
