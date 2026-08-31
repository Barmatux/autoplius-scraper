(function () {
  function clamp(index, length) {
    if (index < 0) return length - 1;
    if (index >= length) return 0;
    return index;
  }

  function setupCarousel(root) {
    var photos;
    try {
      photos = JSON.parse(root.getAttribute("data-photos") || "[]");
    } catch (err) {
      photos = [];
    }
    if (photos.length < 2) return;

    var img = root.querySelector("[data-list-photo]");
    var counter = root.querySelector("[data-list-photo-counter]");
    if (!img) return;

    var index = 0;

    function show(nextIndex) {
      index = clamp(nextIndex, photos.length);
      img.src = photos[index];
      if (counter) counter.textContent = index + 1 + "/" + photos.length;
    }

    root.addEventListener("click", function (event) {
      var target = event.target.closest("[data-list-photo-prev], [data-list-photo-next]");
      if (!target) return;
      event.preventDefault();
      event.stopPropagation();
      if (target.hasAttribute("data-list-photo-prev")) show(index - 1);
      else show(index + 1);
    });
  }

  document.querySelectorAll("[data-list-gallery]").forEach(setupCarousel);
})();
