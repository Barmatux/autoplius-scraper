(function () {
  var root = document.querySelector("[data-city-filter]");
  if (!root) return;

  var toggle = root.querySelector("[data-city-filter-toggle]");
  var panel = root.querySelector("[data-city-filter-panel]");
  if (!toggle || !panel) return;

  function closePanel() {
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  }

  function openPanel() {
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
  }

  toggle.addEventListener("click", function (event) {
    event.preventDefault();
    event.stopPropagation();
    if (panel.hidden) openPanel();
    else closePanel();
  });

  panel.addEventListener("click", function (event) {
    event.stopPropagation();
  });

  document.addEventListener("click", function () {
    closePanel();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closePanel();
  });
})();
