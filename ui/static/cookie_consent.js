/**
 * Cookie / analytics consent for EuroHUB.
 * - necessary: session after login, UI prefs in localStorage (no Metrika)
 * - analytics: load Yandex.Metrika (cookies from mc.yandex.ru)
 */
(function () {
  var STORAGE_KEY = "eu2_cookie_consent";
  var METRIKA_ID = 112311967;
  var banner = document.querySelector("[data-cookie-consent]");
  var acceptBtn = document.querySelector("[data-cookie-accept]");
  var necessaryBtn = document.querySelector("[data-cookie-necessary]");

  function getConsent() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "";
    } catch (err) {
      return "";
    }
  }

  function setConsent(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (err) {
      /* ignore quota / private mode */
    }
  }

  function hideBanner() {
    if (!banner) return;
    banner.hidden = true;
    document.body.classList.remove("cookie-consent-visible");
  }

  function showBanner() {
    if (!banner) return;
    banner.hidden = false;
    document.body.classList.add("cookie-consent-visible");
  }

  function loadMetrika() {
    if (window.__eu2MetrikaLoaded) return;
    window.__eu2MetrikaLoaded = true;

    (function (m, e, t, r, i, k, a) {
      m[i] =
        m[i] ||
        function () {
          (m[i].a = m[i].a || []).push(arguments);
        };
      m[i].l = 1 * new Date();
      for (var j = 0; j < document.scripts.length; j++) {
        if (document.scripts[j].src === r) return;
      }
      k = e.createElement(t);
      a = e.getElementsByTagName(t)[0];
      k.async = 1;
      k.src = r;
      a.parentNode.insertBefore(k, a);
    })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js?id=" + METRIKA_ID, "ym");

    window.ym(METRIKA_ID, "init", {
      ssr: true,
      webvisor: true,
      clickmap: true,
      ecommerce: "dataLayer",
      referrer: document.referrer,
      url: location.href,
      accurateTrackBounce: true,
      trackLinks: true,
    });
  }

  function applyConsent(value) {
    setConsent(value);
    hideBanner();
    if (value === "analytics") {
      loadMetrika();
    }
  }

  var existing = getConsent();
  if (existing === "analytics") {
    hideBanner();
    loadMetrika();
  } else if (existing === "necessary") {
    hideBanner();
  } else {
    showBanner();
  }

  if (acceptBtn) {
    acceptBtn.addEventListener("click", function () {
      applyConsent("analytics");
    });
  }
  if (necessaryBtn) {
    necessaryBtn.addEventListener("click", function () {
      applyConsent("necessary");
    });
  }
})();
