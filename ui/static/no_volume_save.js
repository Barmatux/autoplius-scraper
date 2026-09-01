(function () {
  function setStatus(editor, message, kind) {
    const status = editor.querySelector("[data-no-volume-status]");
    if (!status) {
      return;
    }
    status.textContent = message || "";
    status.className = "no-volume-status" + (kind ? " is-" + kind : "");
  }

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
    const next = Math.max(0, current + delta);
    tabCount.textContent = String(next);
  }

  function removeListingRow(row) {
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
  }

  async function saveVolume(editor) {
    const row = editor.closest("[data-listing-row]");
    const input = editor.querySelector(".no-volume-input");
    const button = editor.querySelector(".no-volume-save");
    if (!row || !input || !button) {
      return;
    }

    const listingId = row.getAttribute("data-listing-row");
    const raw = input.value.trim();
    if (!raw) {
      setStatus(editor, "Укажите объём", "error");
      input.focus();
      return;
    }

    button.disabled = true;
    setStatus(editor, "Сохранение…", "pending");

    try {
      const response = await fetch("/api/listings/" + listingId + "/engine-volume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ liters: raw }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error((data && data.error) || "save failed");
      }
      removeListingRow(row);
    } catch (err) {
      button.disabled = false;
      const message =
        err && err.message === "invalid volume"
          ? "Некорректный объём"
          : "Не удалось сохранить";
      setStatus(editor, message, "error");
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest(".no-volume-save");
    if (!button) {
      return;
    }
    const editor = button.closest("[data-no-volume-editor]");
    if (!editor) {
      return;
    }
    saveVolume(editor);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    const input = event.target.closest(".no-volume-input");
    if (!input) {
      return;
    }
    const editor = input.closest("[data-no-volume-editor]");
    if (!editor) {
      return;
    }
    event.preventDefault();
    saveVolume(editor);
  });
})();
