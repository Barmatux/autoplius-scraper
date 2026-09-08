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
    menu.style.width = "auto";
    menu.style.maxWidth = `${Math.max(280, window.innerWidth - padding * 2)}px`;
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
  }

  function closeSides(root) {
    root.querySelectorAll("[data-nav-side-trigger]").forEach(function (trigger) {
      trigger.classList.remove("is-active");
      trigger.setAttribute("aria-expanded", "false");
    });
    root.querySelectorAll("[data-nav-side]").forEach(function (side) {
      side.setAttribute("hidden", "");
    });
  }

  function openSide(root, key) {
    closeSides(root);
    if (!key) {
      return;
    }
    const trigger = root.querySelector('[data-nav-side-trigger="' + key + '"]');
    const side = root.querySelector('[data-nav-side="' + key + '"]');
    if (!trigger || !side) {
      return;
    }
    trigger.classList.add("is-active");
    trigger.setAttribute("aria-expanded", "true");
    side.removeAttribute("hidden");
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
      menu.style.maxWidth = "";
      closeSides(root);
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

    root.querySelectorAll("[data-nav-side-trigger]").forEach(function (sideTrigger) {
      sideTrigger.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        const key = sideTrigger.getAttribute("data-nav-side-trigger");
        const isOpen = sideTrigger.getAttribute("aria-expanded") === "true";
        if (isOpen) {
          closeSides(root);
        } else {
          openSide(root, key);
        }
        positionMenu(root, menu);
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
