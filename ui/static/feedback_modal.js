(function () {
  const modal = document.querySelector("[data-feedback-modal]");
  if (!modal) {
    return;
  }

  const steps = modal.querySelectorAll("[data-feedback-step]");
  const forms = modal.querySelectorAll("[data-feedback-form]");
  const listingRef = modal.querySelector("[data-feedback-listing-ref]");
  const listingFields = modal.querySelectorAll("[data-feedback-listing-field]");
  let listingContext = null;

  function setStep(name) {
    const target = name || "home";
    steps.forEach((step) => {
      const active = step.getAttribute("data-feedback-step") === target;
      step.classList.toggle("is-active", active);
      step.hidden = !active;
    });
  }

  function setListingContext(el) {
    const id = (el && el.getAttribute("data-feedback-listing")) || "";
    const title = (el && el.getAttribute("data-feedback-title")) || "";
    listingContext = id
      ? {
          id,
          title: title || ("#" + id),
          url: id ? "/listing/" + encodeURIComponent(id) : "",
        }
      : null;

    listingFields.forEach((field) => {
      field.value = listingContext ? listingContext.id : "";
    });

    if (listingRef) {
      if (listingContext) {
        listingRef.hidden = false;
        listingRef.textContent = "По объявлению: " + listingContext.title;
      } else {
        listingRef.hidden = true;
        listingRef.textContent = "";
      }
    }
  }

  function openModal(stepName, opener) {
    setListingContext(opener || null);
    modal.hidden = false;
    document.body.classList.add("feedback-modal-open");
    setStep(stepName || "home");
    const focusEl = modal.querySelector(
      ".feedback-step.is-active .feedback-cta, .feedback-step.is-active input, .feedback-step.is-active textarea"
    );
    if (focusEl) {
      focusEl.focus();
    }
  }

  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove("feedback-modal-open");
    setStep("home");
  }

  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-feedback-open]");
    if (opener) {
      event.preventDefault();
      const step = opener.getAttribute("data-feedback-open") || "home";
      openModal(step === "callback" || step === "message" ? step : "home", opener);
      return;
    }

    const goto = event.target.closest("[data-feedback-goto]");
    if (goto && modal.contains(goto)) {
      event.preventDefault();
      setStep(goto.getAttribute("data-feedback-goto") || "home");
      return;
    }

    const closer = event.target.closest("[data-feedback-close]");
    if (closer && modal.contains(closer)) {
      event.preventDefault();
      closeModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });

  function setStatus(form, text, ok) {
    const status = form.querySelector("[data-feedback-status]");
    if (!status) {
      return;
    }
    status.hidden = !text;
    status.textContent = text || "";
    status.classList.toggle("is-ok", Boolean(ok));
    status.classList.toggle("is-error", Boolean(text) && !ok);
  }

  forms.forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const kind = form.getAttribute("data-feedback-form") || "message";
      const submit = form.querySelector('button[type="submit"]');
      let body = (form.elements.body && form.elements.body.value) || "";
      if (listingContext) {
        const note = "Объявление: " + listingContext.title + (listingContext.url ? " (" + listingContext.url + ")" : "");
        body = body ? body + "\n\n" + note : note;
      }
      const payload = {
        kind,
        phone: (form.elements.phone && form.elements.phone.value) || "",
        name: (form.elements.name && form.elements.name.value) || "",
        body,
        page_url: listingContext && listingContext.url
          ? window.location.origin + listingContext.url
          : window.location.href,
      };
      setStatus(form, "Отправляем…", true);
      if (submit) {
        submit.disabled = true;
      }
      try {
        const response = await fetch("/feedback", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error((data && data.error) || "Не удалось отправить");
        }
        setStatus(
          form,
          kind === "callback"
            ? "Заявка принята. Мы перезвоним."
            : "Сообщение отправлено администратору.",
          true
        );
        form.reset();
        listingFields.forEach((field) => {
          field.value = listingContext ? listingContext.id : "";
        });
      } catch (err) {
        setStatus(form, err.message || "Ошибка отправки", false);
      } finally {
        if (submit) {
          submit.disabled = false;
        }
      }
    });
  });
})();
