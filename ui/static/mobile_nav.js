(function () {
  const toggle = document.querySelector("[data-mobile-nav-toggle]");
  const panel = document.querySelector("[data-mobile-nav-panel]");
  if (!toggle || !panel) {
    return;
  }

  function setOpen(open) {
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    toggle.classList.toggle("is-open", open);
    panel.hidden = !open;
  }

  toggle.addEventListener("click", () => {
    setOpen(panel.hidden);
  });

  document.addEventListener("click", (event) => {
    if (panel.hidden) {
      return;
    }
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    if (target.closest("[data-mobile-nav-toggle]") || target.closest("[data-mobile-nav-panel]")) {
      return;
    }
    setOpen(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      setOpen(false);
    }
  });

  document.querySelectorAll("[data-mobile-nav-group]").forEach((group) => {
    const trigger = group.querySelector("[data-mobile-nav-group-trigger]");
    const submenu = group.querySelector("[data-mobile-nav-submenu]");
    if (!trigger || !submenu) {
      return;
    }
    trigger.addEventListener("click", () => {
      const open = submenu.hidden;
      submenu.hidden = !open;
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
      group.classList.toggle("is-open", open);
    });
  });
})();
