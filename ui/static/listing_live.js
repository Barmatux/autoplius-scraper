(function () {
  const nodes = document.querySelectorAll("[data-listing-live]");
  if (!nodes.length) {
    return;
  }

  nodes.forEach(function (node) {
    const listingId = node.getAttribute("data-listing-id");
    if (!listingId) {
      return;
    }

    fetch("/api/listing/" + encodeURIComponent(listingId) + "/live", {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("live check failed");
        }
        return response.json();
      })
      .then(function (payload) {
        if (!payload || payload.status !== "available") {
          return;
        }
        node.hidden = false;
        node.classList.add("is-available");
        node.setAttribute("title", "Объявление доступно на Autoplius");
        node.setAttribute("aria-label", "Объявление доступно на Autoplius");
        node.textContent = "✓";
      })
      .catch(function () {
        /* keep status hidden on errors */
      });
  });
})();
