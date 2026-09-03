(function () {
  const root = document.querySelector("[data-import-presets]");
  if (!root) {
    return;
  }

  const trigger = root.querySelector("[data-import-presets-trigger]");
  const menu = root.querySelector("[data-import-presets-menu]");
  if (!trigger || !menu) {
    return;
  }

  function positionMenu() {
    const rect = trigger.getBoundingClientRect();
    const gap = 6;
    const padding = 8;
    const menuWidth = Math.min(
      Math.max(menu.offsetWidth || 320, rect.width),
      window.innerWidth - padding * 2
    );
    let left = rect.left;
    if (left + menuWidth > window.innerWidth - padding) {
      left = window.innerWidth - padding - menuWidth;
    }
    if (left < padding) {
      left = padding;
    }
    menu.style.top = `${Math.round(rect.bottom + gap)}px`;
    menu.style.left = `${Math.round(left)}px`;
    menu.style.width = `${Math.round(menuWidth)}px`;
  }

  function setOpen(open) {
    root.classList.toggle("is-open", open);
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      menu.removeAttribute("hidden");
      positionMenu();
    } else {
      menu.setAttribute("hidden", "");
      menu.style.top = "";
      menu.style.left = "";
      menu.style.width = "";
    }
  }

  setOpen(false);

  trigger.addEventListener("click", function (event) {
    event.preventDefault();
    event.stopPropagation();
    setOpen(!root.classList.contains("is-open"));
  });

  document.addEventListener("click", function (event) {
    if (!root.contains(event.target)) {
      setOpen(false);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setOpen(false);
    }
  });

  window.addEventListener(
    "resize",
    function () {
      if (root.classList.contains("is-open")) {
        positionMenu();
      }
    },
    { passive: true }
  );

  window.addEventListener(
    "scroll",
    function () {
      if (root.classList.contains("is-open")) {
        positionMenu();
      }
    },
    { passive: true, capture: true }
  );

  menu.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      setOpen(false);
    });
  });
})();
