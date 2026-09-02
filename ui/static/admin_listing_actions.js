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

  function adjustTabCount(hrefPart, delta) {
    const tabCount = document.querySelector(
      '.tabs a[href*="' + hrefPart + '"] .tab-count'
    );
    if (!tabCount) {
      return;
    }
    const current = parseInt(tabCount.textContent, 10);
    if (Number.isNaN(current)) {
      return;
    }
    tabCount.textContent = String(Math.max(0, current + delta));
  }

  function removeListingRow(row, { fromNoVolume, toElectric } = {}) {
    row.style.transition = "opacity 0.2s ease";
    row.style.opacity = "0";
    window.setTimeout(() => {
      row.remove();
      adjustSummaryCount(-1);
      if (fromNoVolume) {
        adjustTabCount("tab=no_volume", -1);
      }
      if (toElectric) {
        adjustTabCount("tab=electric", 1);
      }
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
      const cards = document.querySelector(".listings-feed");
      if (cards && !cards.querySelector("[data-listing-card]")) {
        cards.insertAdjacentHTML(
          "afterend",
          '<p class="empty">Нет объявлений в базе по фильтру.</p>'
        );
        cards.remove();
      }
    }, 200);
  }

  function submitAdminForm(form, { fromNoVolume, toElectric, failMessage }) {
    const row =
      form.closest("[data-listing-row]") || form.closest("[data-listing-card]");
    if (!row) {
      return;
    }

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
          throw new Error(data.error || "request failed");
        }
        removeListingRow(row, { fromNoVolume, toElectric });
      })
      .catch(() => {
        if (button) {
          button.disabled = false;
        }
        window.alert(failMessage);
      });
  }

  document.addEventListener("submit", (event) => {
    const archiveForm = event.target.closest("[data-admin-archive-form]");
    if (archiveForm) {
      event.preventDefault();
      const onNoVolume = (archiveForm.querySelector('input[name="tab"]')?.value || "") === "no_volume";
      submitAdminForm(archiveForm, {
        fromNoVolume: onNoVolume,
        failMessage: "Не удалось отправить объявление в архив",
      });
      return;
    }

    const electricForm = event.target.closest("[data-admin-electric-form]");
    if (electricForm) {
      event.preventDefault();
      submitAdminForm(electricForm, {
        fromNoVolume: true,
        toElectric: true,
        failMessage: "Не удалось перенести объявление в Электро",
      });
    }
  });
})();
