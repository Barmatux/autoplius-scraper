(function () {
  function adjustSummaryCount(delta) {
    const summary = document.querySelector(".summary strong");
    if (!summary) {
      return;
    }
    const current = parseInt(summary.textContent, 10);
    if (Number.isNaN(current)) {
      return;
    }
    summary.textContent = String(Math.max(0, current + delta));
  }

  function adjustNoVolumeTabCount(delta) {
    const tabCount = document.querySelector('.tabs a[href*="tab=no_volume"] .tab-count');
    if (!tabCount) {
      return;
    }
    const current = parseInt(tabCount.textContent, 10);
    if (Number.isNaN(current)) {
      return;
    }
    tabCount.textContent = String(Math.max(0, current + delta));
  }

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-admin-archive-form]");
    if (!form) {
      return;
    }

    const row = form.closest("[data-listing-row]");
    if (!row) {
      return;
    }

    event.preventDefault();

    const button = form.querySelector('button[type="submit"]');
    if (button?.disabled) {
      return;
    }

    if (button) {
      button.disabled = true;
    }

    fetch(form.action, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then((response) => response.json().then((data) => ({ response, data })))
      .then(({ response, data }) => {
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "archive failed");
        }
        row.style.transition = "opacity 0.2s ease";
        row.style.opacity = "0";
        window.setTimeout(() => {
          row.remove();
          adjustSummaryCount(-1);
          adjustNoVolumeTabCount(-1);
          const tbody = document.querySelector(".listings-table tbody");
          if (tbody && !tbody.querySelector("[data-listing-row]")) {
            const tableWrap = document.querySelector(".table-wrap");
            if (tableWrap) {
              tableWrap.insertAdjacentHTML(
                "afterend",
                '<p class="empty">Нет объявлений в базе по фильтру.</p>'
              );
              tableWrap.remove();
            }
          }
        }, 200);
      })
      .catch(() => {
        if (button) {
          button.disabled = false;
        }
        window.alert("Не удалось отправить объявление в архив");
      });
  });
})();
