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

  function setOpen(open) {
    root.classList.toggle("is-open", open);
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    menu.hidden = !open;
  }

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

  menu.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      setOpen(false);
    });
  });
})();
