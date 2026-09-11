(() => {
  const form = document.getElementById("customs-calc-form");
  if (!form) return;

  const resultEl = document.getElementById("customs-calc-result");
  const errorEl = document.getElementById("customs-calc-error");
  const volumeWrap = document.getElementById("calc-volume-wrap");
  const privilegeWrap = document.getElementById("calc-privilege-wrap");
  const priceWrap = document.getElementById("calc-price-wrap");
  const priceInput = form.querySelector('input[name="price_eur"]');
  const asideEl = document.getElementById("calc-aside-placeholder");

  const money = (value, digits = 0) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString("ru-RU", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  };

  const syncFields = () => {
    const kind = form.querySelector('input[name="vehicle_kind"]:checked')?.value || "ice";
    const person = form.querySelector('input[name="person"]:checked')?.value || "individual";
    const age = form.querySelector('select[name="age_band"]')?.value || "3_5";
    const needsVolume = kind === "ice";
    const canPrivilege = kind === "ice" && person === "individual";
    // Стоимость влияет на пошлину для авто <3 лет (ЕАЭС) и всегда для EV/EREV.
    const needsPrice = age === "under_3" || kind === "electric" || kind === "erev";
    if (volumeWrap) volumeWrap.hidden = !needsVolume;
    if (privilegeWrap) privilegeWrap.hidden = !canPrivilege;
    if (priceWrap) priceWrap.hidden = !needsPrice;
    if (priceInput) {
      priceInput.required = needsPrice;
      if (!needsPrice) priceInput.value = "";
    }
  };

  const renderResult = (data) => {
    if (!resultEl) return;
    if (!data.ok) {
      resultEl.hidden = true;
      if (asideEl) asideEl.hidden = false;
      if (errorEl) {
        errorEl.hidden = false;
        errorEl.textContent = data.error || "Не удалось рассчитать.";
      }
      return;
    }
    if (errorEl) errorEl.hidden = true;
    if (asideEl) asideEl.hidden = true;

    const lines = [];
    if (data.price_eur > 0) {
      lines.push(["Стоимость авто", `${money(data.price_eur)} €`]);
    }
    lines.push(["Возраст для ставки", data.age_band_label]);
    if (data.engine_cm3) {
      lines.push(["Объём двигателя", `${money(data.engine_cm3)} см³`]);
    }
    lines.push(["Ставка", data.duty_rate_label]);
    if (data.privilege_applied) {
      lines.push(["Пошлина без льготы", `${money(data.duty_full_eur, 2)} €`]);
      lines.push(["Пошлина со льготой 50%", `${money(data.duty_payable_eur, 2)} €`]);
    } else {
      lines.push(["Таможенная пошлина", `${money(data.duty_payable_eur, 2)} €`]);
    }
    if (data.vat_eur > 0) {
      lines.push(["НДС", `${money(data.vat_eur, 2)} €`]);
    }
    lines.push(
      ["Утилизационный сбор", `${money(data.utilization_byn, 2)} Br`],
      ["Таможенный сбор", `${money(data.customs_fee_byn, 2)} Br`],
      ["Услуги декларанта", `${money(data.declarant_byn, 2)} Br`],
      ["ЭПТС", `${money(data.epts_byn, 2)} Br`],
      ["Сборы (всего)", `${money(data.fees_byn, 2)} Br ≈ ${money(data.fees_eur, 2)} €`],
      ["Таможенные платежи", `${money(data.payments_eur, 2)} € / ${money(data.payments_usd)} $`],
    );

    const notes = (data.notes || [])
      .map((n) => `<li>${n}</li>`)
      .join("");

    const totalLabel =
      data.price_eur > 0 ? "Авто + таможенные платежи" : "Итого таможенные платежи";

    resultEl.hidden = false;
    resultEl.innerHTML = `
      <h2 class="calc-result-title">Результаты расчёта</h2>
      <ul class="calc-result-lines">
        ${lines
          .map(
            ([k, v]) =>
              `<li><span class="calc-result-key">${k}</span><span class="calc-result-val">${v}</span></li>`,
          )
          .join("")}
      </ul>
      <div class="calc-result-total">
        <div class="calc-result-total-label">${totalLabel}</div>
        <div class="calc-result-total-values">
          <strong>${money(data.total_eur)}</strong>&nbsp;€
          <span class="calc-result-or">или</span>
          <strong>${money(data.total_usd)}</strong>&nbsp;$
          <span class="calc-result-or">≈</span>
          <strong>${money(data.total_byn)}</strong>&nbsp;Br
        </div>
      </div>
      <ul class="calc-result-notes">${notes}</ul>
      <p class="calc-result-cta">
        <a class="nav-btn nav-btn-text" href="/?tab=all">Смотреть авто из Европы</a>
      </p>
    `;
    resultEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  form.addEventListener("change", syncFields);
  syncFields();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(form);
    const age = String(fd.get("age_band") || "");
    const kind = String(fd.get("vehicle_kind") || "ice");
    const needsPrice = age === "under_3" || kind === "electric" || kind === "erev";
    const rawPrice = fd.get("price_eur");
    const payload = {
      price_eur: needsPrice && rawPrice !== "" ? Number(rawPrice) : 0,
      age_band: age,
      vehicle_kind: kind,
      person: String(fd.get("person") || "individual"),
      engine_cm3: fd.get("engine_cm3") ? Number(fd.get("engine_cm3")) : null,
      privilege_50: fd.get("privilege_50") === "on",
    };

    if (errorEl) {
      errorEl.hidden = true;
      errorEl.textContent = "";
    }

    try {
      const res = await fetch("/api/customs-calculator", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      renderResult(data);
    } catch (_err) {
      renderResult({ ok: false, error: "Сеть недоступна. Попробуйте ещё раз." });
    }
  });
})();
