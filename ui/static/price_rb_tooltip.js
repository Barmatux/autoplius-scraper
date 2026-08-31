(function () {
  var activeTip = null;

  function hideTip() {
    if (!activeTip) return;
    activeTip.hidden = true;
    activeTip.style.left = "";
    activeTip.style.top = "";
    activeTip = null;
  }

  function placeTip(anchor, tip) {
    tip.hidden = false;
    tip.style.left = "0px";
    tip.style.top = "0px";
    var anchorRect = anchor.getBoundingClientRect();
    var tipRect = tip.getBoundingClientRect();
    var gap = 8;
    var left = anchorRect.left;
    var top = anchorRect.bottom + gap;

    if (left + tipRect.width > window.innerWidth - 12) {
      left = Math.max(12, window.innerWidth - tipRect.width - 12);
    }
    if (top + tipRect.height > window.innerHeight - 12) {
      top = Math.max(12, anchorRect.top - tipRect.height - gap);
    }
    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
  }

  document.addEventListener("mouseover", function (event) {
    var host = event.target.closest(".price-rb");
    if (!host) return;
    var tip = host.querySelector(".price-rb-tooltip");
    if (!tip) return;
    if (activeTip && activeTip !== tip) hideTip();
    activeTip = tip;
    placeTip(host, tip);
  });

  document.addEventListener("mouseout", function (event) {
    var host = event.target.closest(".price-rb");
    if (!host || !activeTip) return;
    var next = event.relatedTarget;
    if (next && (host.contains(next) || activeTip.contains(next))) return;
    hideTip();
  });

  document.addEventListener("focusin", function (event) {
    var host = event.target.closest(".price-rb");
    if (!host) return;
    var tip = host.querySelector(".price-rb-tooltip");
    if (!tip) return;
    if (activeTip && activeTip !== tip) hideTip();
    activeTip = tip;
    placeTip(host, tip);
  });

  document.addEventListener("focusout", function (event) {
    var host = event.target.closest(".price-rb");
    if (!host || !activeTip) return;
    var next = event.relatedTarget;
    if (next && (host.contains(next) || activeTip.contains(next))) return;
    hideTip();
  });

  window.addEventListener("scroll", hideTip, true);
  window.addEventListener("resize", hideTip);
})();
