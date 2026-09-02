(function () {
  const toggle = document.querySelector("[data-mobile-nav-toggle]");
  const shell = document.querySelector("[data-mobile-nav-shell]");
  if (!toggle || !shell) {
    return;
  }

  const backdrop = shell.querySelector("[data-mobile-nav-backdrop]");

  function setOpen(open) {
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    toggle.classList.toggle("is-open", open);
    document.body.classList.toggle("mobile-nav-open", open);
    shell.hidden = !open;
  }

  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    setOpen(shell.hidden);
  });

  if (backdrop) {
    backdrop.addEventListener("click", () => setOpen(false));
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !shell.hidden) {
      setOpen(false);
    }
  });

  shell.querySelectorAll("[data-mobile-nav-group]").forEach((group) => {
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
