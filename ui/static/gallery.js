(function () {
  var root = document.querySelector("[data-gallery]");
  if (!root) return;

  var photos;
  try {
    photos = JSON.parse(root.getAttribute("data-photos") || "[]");
  } catch (err) {
    photos = [];
  }
  if (!photos.length) return;

  var index = 0;
  var hero = root.querySelector("[data-gallery-hero]");
  var counter = root.querySelector("[data-gallery-counter]");
  var thumbs = Array.prototype.slice.call(root.querySelectorAll("[data-gallery-thumb]"));
  var lightbox = document.querySelector("[data-lightbox]");
  var lightboxImg = lightbox ? lightbox.querySelector("[data-lightbox-img]") : null;
  var lightboxCounter = lightbox ? lightbox.querySelector("[data-lightbox-counter]") : null;
  var lightboxOpen = false;

  function clamp(i) {
    if (i < 0) return photos.length - 1;
    if (i >= photos.length) return 0;
    return i;
  }

  function setActiveThumb(i) {
    thumbs.forEach(function (btn, idx) {
      btn.classList.toggle("is-active", idx === i);
    });
  }

  function show(i) {
    index = clamp(i);
    var src = photos[index];
    if (hero) hero.src = src;
    if (lightboxImg && lightboxOpen) lightboxImg.src = src;
    if (counter) counter.textContent = index + 1 + " / " + photos.length;
    if (lightboxCounter) lightboxCounter.textContent = index + 1 + " / " + photos.length;
    setActiveThumb(index);
  }

  function openLightbox() {
    if (!lightbox || !lightboxImg) return;
    lightboxOpen = true;
    lightboxImg.src = photos[index];
    if (lightboxCounter) lightboxCounter.textContent = index + 1 + " / " + photos.length;
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
  }

  function closeLightbox() {
    if (!lightbox) return;
    lightboxOpen = false;
    lightbox.hidden = true;
    document.body.classList.remove("lightbox-open");
  }

  root.addEventListener("click", function (event) {
    var target = event.target.closest("[data-gallery-prev], [data-gallery-next], [data-gallery-thumb], [data-gallery-hero]");
    if (!target) return;
    event.preventDefault();
    if (target.hasAttribute("data-gallery-prev")) {
      show(index - 1);
      return;
    }
    if (target.hasAttribute("data-gallery-next")) {
      show(index + 1);
      return;
    }
    if (target.hasAttribute("data-gallery-thumb")) {
      var thumbIndex = Number(target.getAttribute("data-gallery-thumb"));
      if (!Number.isNaN(thumbIndex)) show(thumbIndex);
      return;
    }
    if (target.hasAttribute("data-gallery-hero")) {
      openLightbox();
    }
  });

  if (lightbox) {
    lightbox.addEventListener("click", function (event) {
      var target = event.target.closest("[data-lightbox-prev], [data-lightbox-next], [data-lightbox-close], [data-lightbox-backdrop]");
      if (!target) return;
      event.preventDefault();
      if (target.hasAttribute("data-lightbox-prev")) {
        show(index - 1);
        return;
      }
      if (target.hasAttribute("data-lightbox-next")) {
        show(index + 1);
        return;
      }
      closeLightbox();
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && lightboxOpen) {
      closeLightbox();
      return;
    }
    if (photos.length < 2) return;
    if (event.key === "ArrowLeft") show(index - 1);
    if (event.key === "ArrowRight") show(index + 1);
  });

  show(0);
})();
