(function () {
  function setFavoriteState(form, isFavorite) {
    const button = form.querySelector(".favorite-btn");
    const icon = form.querySelector(".favorite-icon");
    if (!button || !icon) {
      return;
    }
    button.classList.toggle("is-active", isFavorite);
    button.setAttribute("aria-pressed", isFavorite ? "true" : "false");
    button.setAttribute(
      "aria-label",
      isFavorite ? "Убрать из избранного" : "Добавить в избранное"
    );
    button.title = isFavorite ? "Убрать из избранного" : "В избранное";
    icon.textContent = isFavorite ? "★" : "☆";
  }

  function adjustCabinetFavoriteCount(delta) {
    document.querySelectorAll("[data-favorites-count]").forEach((node) => {
      const current = parseInt(node.textContent, 10);
      if (Number.isNaN(current)) {
        return;
      }
      node.textContent = String(Math.max(0, current + delta));
    });
  }

  function removeFavoriteCard(card) {
    card.style.transition = "opacity 0.2s ease";
    card.style.opacity = "0";
    window.setTimeout(() => {
      card.remove();
      adjustCabinetFavoriteCount(-1);
      const grid = document.querySelector("[data-cabinet-favorites]");
      if (grid && !grid.querySelector("[data-listing-card]")) {
        grid.insertAdjacentHTML(
          "afterend",
          '<p class="empty cabinet-favorites-empty" data-favorites-empty>Пока ничего нет. Откройте объявление в каталоге и нажмите ☆, чтобы добавить его сюда.</p>'
        );
        grid.remove();
      }
    }, 200);
  }

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-favorite-form]");
    if (!form) {
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
          throw new Error(data.error || "request failed");
        }
        const card = form.closest("[data-listing-card]");
        if (card && document.querySelector("[data-cabinet-favorites]") && !data.favorited) {
          removeFavoriteCard(card);
          return;
        }
        setFavoriteState(form, Boolean(data.favorited));
        if (document.querySelector("[data-cabinet-favorites]") && data.favorited) {
          adjustCabinetFavoriteCount(1);
        }
      })
      .catch(() => {
        window.alert("Не удалось обновить избранное");
      })
      .finally(() => {
        if (button) {
          button.disabled = false;
        }
      });
  });
})();
