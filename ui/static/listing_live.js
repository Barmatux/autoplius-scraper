(function () {
  const root = document.querySelector("[data-listing-live-root]");
  if (!root) {
    return;
  }

  const listingId = root.getAttribute("data-listing-id");
  const button = root.querySelector("[data-listing-live-check]");
  const statusNode = root.querySelector("[data-listing-live-status]");
  if (!listingId || !button || !statusNode) {
    return;
  }

  function resetStatus() {
    statusNode.hidden = true;
    statusNode.classList.remove("is-available", "is-unavailable", "is-unknown", "is-loading");
    statusNode.removeAttribute("title");
    statusNode.removeAttribute("aria-label");
    statusNode.textContent = "";
  }

  function showStatus(kind, text, title) {
    statusNode.hidden = false;
    statusNode.classList.remove("is-available", "is-unavailable", "is-unknown", "is-loading");
    statusNode.classList.add("is-" + kind);
    statusNode.textContent = text;
    if (title) {
      statusNode.setAttribute("title", title);
      statusNode.setAttribute("aria-label", title);
    }
  }

  button.addEventListener("click", function () {
    if (button.disabled) {
      return;
    }
    button.disabled = true;
    resetStatus();
    showStatus("loading", "…", "Проверка на Autoplius…");

    fetch("/api/listing/" + encodeURIComponent(listingId) + "/live", {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) {
        if (response.status === 401 || response.status === 403) {
          throw new Error("admin only");
        }
        if (!response.ok) {
          throw new Error("live check failed");
        }
        return response.json();
      })
      .then(function (payload) {
        const status = payload && payload.status;
        if (status === "available") {
          showStatus("available", "✓", "Объявление доступно на Autoplius");
          return;
        }
        if (status === "unavailable") {
          showStatus("unavailable", "✕", "Объявление недоступно на Autoplius");
          return;
        }
        showStatus("unknown", "?", "Не удалось проверить актуальность");
      })
      .catch(function () {
        showStatus("unknown", "?", "Ошибка проверки");
      })
      .finally(function () {
        button.disabled = false;
      });
  });
})();
