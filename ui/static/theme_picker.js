(function () {
  var STORAGE_KEY = "eu2-site-theme";
  var DEFAULT_THEME = "docs";
  var PUBLIC_THEMES = ["docs"];
  var ADMIN_THEMES = ["original", "docs", "parchment", "forest", "carbon"];

  function isAdmin() {
    return window.__EU2_IS_ADMIN__ === true || window.__EU2_IS_ADMIN__ === "true";
  }

  function allowedThemes() {
    return isAdmin() ? ADMIN_THEMES : PUBLIC_THEMES;
  }

  function currentTheme() {
    var allowed = allowedThemes();
    try {
      var value = localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
      return allowed.indexOf(value) >= 0 ? value : DEFAULT_THEME;
    } catch (err) {
      return DEFAULT_THEME;
    }
  }

  function applyTheme(themeId) {
    var allowed = allowedThemes();
    var id = allowed.indexOf(themeId) >= 0 ? themeId : DEFAULT_THEME;
    if (id === "original") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", id);
    }
    if (isAdmin()) {
      try {
        localStorage.setItem(STORAGE_KEY, id);
      } catch (err) {
        /* ignore quota / private mode */
      }
    }
    document.querySelectorAll("[data-theme-id]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-theme-id") === id);
    });
  }

  function openPicker() {
    if (!isAdmin()) return;
    var backdrop = document.querySelector("[data-theme-backdrop]");
    if (!backdrop) return;
    applyTheme(currentTheme());
    backdrop.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closePicker() {
    var backdrop = document.querySelector("[data-theme-backdrop]");
    if (!backdrop) return;
    backdrop.hidden = true;
    document.body.style.overflow = "";
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(currentTheme());

    document.querySelectorAll("[data-theme-open]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        openPicker();
      });
    });

    document.querySelectorAll("[data-theme-close]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        closePicker();
      });
    });

    var backdrop = document.querySelector("[data-theme-backdrop]");
    if (backdrop) {
      backdrop.addEventListener("click", function (e) {
        if (e.target === backdrop) closePicker();
      });
    }

    document.querySelectorAll("[data-theme-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyTheme(btn.getAttribute("data-theme-id"));
      });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePicker();
    });
  });
})();
