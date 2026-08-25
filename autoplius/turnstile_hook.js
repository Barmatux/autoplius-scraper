(() => {
  if (window.__autopliusTurnstileHookInstalled) {
    return;
  }
  window.__autopliusTurnstileHookInstalled = true;

  const originalClear = console.clear;
  console.clear = () => {};

  const report = (payload) => {
    window.__cfTurnstileParams = payload;
    if (typeof window.__reportTurnstileParams === "function") {
      window.__reportTurnstileParams(JSON.stringify(payload));
    }
  };

  const hookRender = () => {
    if (!window.turnstile || !window.turnstile.render) {
      return false;
    }
    const originalRender = window.turnstile.render.bind(window.turnstile);
    window.turnstile.render = (container, options) => {
      const payload = {
        websiteKey: options.sitekey,
        websiteURL: window.location.href,
        action: options.action,
        data: options.cData,
        pagedata: options.chlPageData,
      };
      window.__cfTurnstileCallback = options.callback;
      report(payload);
      return "autoplius-turnstile-intercept";
    };
    return true;
  };

  if (!hookRender()) {
    const timer = setInterval(() => {
      if (hookRender()) {
        clearInterval(timer);
      }
    }, 25);
    setTimeout(() => clearInterval(timer), 120000);
  }
})();
