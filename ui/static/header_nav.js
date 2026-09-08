(function () {
  const dropdowns = Array.from(document.querySelectorAll("[data-nav-dropdown]"));
  if (!dropdowns.length) {
    return;
  }

  function positionMenu(root, menu) {
    const trigger = root.querySelector("[data-nav-dropdown-trigger]");
    if (!trigger || !menu) {
      return;
    }
    const rect = trigger.getBoundingClientRect();
    const gap = 6;
    const padding = 8;
    const menuWidth = Math.min(
      Math.max(menu.offsetWidth || 280, rect.width),
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

  function closeSubmenus(root) {
    root.querySelectorAll("[data-nav-submenu]").forEach(function (sub) {
      sub.classList.remove("is-open");
      const trigger = sub.querySelector("[data-nav-submenu-trigger]");
      const menu = sub.querySelector("[data-nav-submenu-menu]");
      if (trigger) {
        trigger.setAttribute("aria-expanded", "false");
      }
      if (menu) {
        menu.setAttribute("hidden", "");
      }
    });
  }

  function setOpen(root, open) {
    const trigger = root.querySelector("[data-nav-dropdown-trigger]");
    const menu = root.querySelector("[data-nav-dropdown-menu]");
    if (!trigger || !menu) {
      return;
    }
    root.classList.toggle("is-open", open);
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      menu.removeAttribute("hidden");
      positionMenu(root, menu);
    } else {
      menu.setAttribute("hidden", "");
      menu.style.top = "";
      menu.style.left = "";
      menu.style.width = "";
      closeSubmenus(root);
    }
  }

  function closeAll(except) {
    dropdowns.forEach(function (root) {
      if (root !== except) {
        setOpen(root, false);
      }
    });
  }

  dropdowns.forEach(function (root) {
    const trigger = root.querySelector("[data-nav-dropdown-trigger]");
    const menu = root.querySelector("[data-nav-dropdown-menu]");
    if (!trigger || !menu) {
      return;
    }

    setOpen(root, false);

    trigger.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      const willOpen = !root.classList.contains("is-open");
      closeAll(root);
      setOpen(root, willOpen);
    });

    root.querySelectorAll("[data-nav-submenu]").forEach(function (sub) {
      const subTrigger = sub.querySelector("[data-nav-submenu-trigger]");
      const subMenu = sub.querySelector("[data-nav-submenu-menu]");
      if (!subTrigger || !subMenu) {
        return;
      }
      subTrigger.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        const willOpen = !sub.classList.contains("is-open");
        closeSubmenus(root);
        sub.classList.toggle("is-open", willOpen);
        subTrigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
        if (willOpen) {
          subMenu.removeAttribute("hidden");
        } else {
          subMenu.setAttribute("hidden", "");
        }
      });
    });

    menu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        setOpen(root, false);
      });
    });
  });

  document.addEventListener("click", function (event) {
    if (!event.target.closest("[data-nav-dropdown]")) {
      closeAll();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeAll();
    }
  });

  function repositionOpen() {
    dropdowns.forEach(function (root) {
      if (!root.classList.contains("is-open")) {
        return;
      }
      const menu = root.querySelector("[data-nav-dropdown-menu]");
      if (menu) {
        positionMenu(root, menu);
      }
    });
  }

  window.addEventListener("resize", repositionOpen, { passive: true });
  window.addEventListener("scroll", repositionOpen, { passive: true, capture: true });
})();
