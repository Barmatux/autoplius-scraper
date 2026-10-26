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
  const catalogWrap = document.getElementById("calc-catalog-wrap");
  const makeSelect = document.getElementById("calc-make");
  const modelSelect = document.getElementById("calc-model");
  const engineSelect = document.getElementById("calc-engine");
  const volumeInput = document.getElementById("calc-volume");
  const catalogHint = document.getElementById("calc-catalog-hint");
  const catalogNode = document.getElementById("calc-catalog-data");

  const EMPTY_MODEL = "__empty__";
  let entries = [];
  try {
    entries = JSON.parse(catalogNode ? catalogNode.textContent || "[]" : "[]");
  } catch (_err) {
    entries = [];
  }
  if (!Array.isArray(entries)) entries = [];

  const money = (value, digits = 0) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString("ru-RU", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  };

  const escapeHtml = (text) =>
    String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  const uniqueSorted = (values) => {
    const seen = Object.create(null);
    const out = [];
    values.forEach((value) => {
      const key = String(value == null ? "" : value);
      if (seen[key]) return;
      seen[key] = true;
      out.push(key);
    });
    out.sort((a, b) => a.localeCompare(b, "ru", { sensitivity: "base" }));
    return out;
  };

  const modelOptionValue = (model) => (model ? model : EMPTY_MODEL);
  const modelFromOption = (value) => (value === EMPTY_MODEL ? "" : value);

  const volumeForEntry = (entry) => {
    if (!entry) return null;
    if (entry.customs_cm3 != null && entry.customs_cm3 !== "") return Number(entry.customs_cm3);
    if (entry.suggested_cm3 != null && entry.suggested_cm3 !== "") return Number(entry.suggested_cm3);
    return null;
  };

  const selectedEngineEntry = () => {
    const id = engineSelect?.value;
    if (!id) return null;
    return entries.find((entry) => String(entry.id) === String(id)) || null;
  };

  const fillSelect = (select, values, placeholder, selected, mapValue) => {
    if (!select) return;
    const mapper = mapValue || ((value) => value);
    let html = `<option value="">${escapeHtml(placeholder)}</option>`;
    values.forEach((value) => {
      const optionValue = mapper(value);
      const label = value || "—";
      const sel = optionValue === selected ? " selected" : "";
      html += `<option value="${escapeHtml(optionValue)}"${sel}>${escapeHtml(label)}</option>`;
    });
    select.innerHTML = html;
  };

  const setCatalogHint = (message, warn) => {
    if (!catalogHint) return;
    if (!message) {
      catalogHint.hidden = true;
      catalogHint.textContent = "";
      catalogHint.classList.remove("is-warn");
      return;
    }
    catalogHint.hidden = false;
    catalogHint.textContent = message;
    catalogHint.classList.toggle("is-warn", Boolean(warn));
  };

  const syncVolumeFromCatalog = () => {
    const entry = selectedEngineEntry();
    const cm3 = volumeForEntry(entry);
    if (!volumeInput) return;
    if (cm3 != null && Number.isFinite(cm3) && cm3 > 0) {
      volumeInput.value = String(Math.round(cm3));
      setCatalogHint(
        entry.customs_cm3 != null
          ? "Объём взят из растаможка базы"
          : "Ориентировочный объём из объявлений — уточните в растаможка базе",
        entry.customs_cm3 == null,
      );
    } else {
      volumeInput.value = "";
      setCatalogHint(entry ? "Для этой модификации в каталоге нет объёма" : "", Boolean(entry));
    }
  };

  const onMakeChange = () => {
    const make = makeSelect.value;
    modelSelect.disabled = !make;
    engineSelect.disabled = true;
    fillSelect(
      modelSelect,
      make
        ? uniqueSorted(
            entries
              .filter((entry) => entry.make === make)
              .map((entry) => entry.model || ""),
          )
        : [],
      make ? "Выберите модель" : "Сначала марка",
      "",
      modelOptionValue,
    );
    fillSelect(engineSelect, [], "Сначала модель", "");
    if (volumeInput) volumeInput.value = "";
    setCatalogHint("");
  };

  const onModelChange = () => {
    const make = makeSelect.value;
    const model = modelFromOption(modelSelect.value);
    const hasSelection = Boolean(make) && !modelSelect.disabled && modelSelect.selectedIndex > 0;
    engineSelect.disabled = !hasSelection;
    const engineEntries = hasSelection
      ? entries.filter((entry) => entry.make === make && (entry.model || "") === model)
      : [];
    let html = `<option value="">${hasSelection ? "Выберите мотор" : "Сначала модель"}</option>`;
    engineEntries
      .slice()
      .sort((a, b) =>
        String(a.engine_label || "").localeCompare(String(b.engine_label || ""), "ru", {
          sensitivity: "base",
        }),
      )
      .forEach((entry) => {
        let label = entry.engine_label || "—";
        if (entry.fuel) label += ` · ${entry.fuel}`;
        const cm3 = volumeForEntry(entry);
        if (cm3 != null) label += ` · ${Math.round(cm3)} см³`;
        html += `<option value="${escapeHtml(String(entry.id))}">${escapeHtml(label)}</option>`;
      });
    engineSelect.innerHTML = html;
    if (volumeInput) volumeInput.value = "";
    setCatalogHint("");
  };

  const syncFields = () => {
    const kind = form.querySelector('input[name="vehicle_kind"]:checked')?.value || "ice";
    const age = form.querySelector('select[name="age_band"]')?.value || "3_5";
    const needsCatalog = kind === "ice";
    const canPrivilege = kind === "ice";
    const needsPrice = age === "under_3";

    if (catalogWrap) catalogWrap.hidden = !needsCatalog;
    if (volumeWrap) volumeWrap.hidden = !needsCatalog;
    if (privilegeWrap) privilegeWrap.hidden = !canPrivilege;
    if (priceWrap) priceWrap.hidden = !needsPrice;
    if (priceInput) {
      priceInput.required = needsPrice;
      if (!needsPrice) priceInput.value = "";
    }
    if (!needsCatalog) {
      setCatalogHint("");
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

    const notes = (data.notes || []).map((n) => `<li>${escapeHtml(n)}</li>`).join("");
    const totalLabel =
      data.price_eur > 0 ? "Авто + таможенные платежи" : "Итого таможенные платежи";

    resultEl.hidden = false;
    resultEl.innerHTML = `
      <h2 class="calc-result-title">Результаты расчёта</h2>
      <ul class="calc-result-lines">
        ${lines
          .map(
            ([k, v]) =>
              `<li><span class="calc-result-key">${escapeHtml(k)}</span><span class="calc-result-val">${v}</span></li>`,
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

  fillSelect(
    makeSelect,
    uniqueSorted(entries.map((entry) => entry.make)),
    "Выберите марку",
    "",
  );
  fillSelect(modelSelect, [], "Сначала марка", "");
  fillSelect(engineSelect, [], "Сначала модель", "");
  if (modelSelect) modelSelect.disabled = true;
  if (engineSelect) engineSelect.disabled = true;

  makeSelect?.addEventListener("change", onMakeChange);
  modelSelect?.addEventListener("change", onModelChange);
  engineSelect?.addEventListener("change", syncVolumeFromCatalog);

  form.addEventListener("change", syncFields);
  syncFields();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(form);
    const age = String(fd.get("age_band") || "");
    const kind = String(fd.get("vehicle_kind") || "ice");
    const needsPrice = age === "under_3";
    const needsCatalog = kind === "ice";
    const rawPrice = fd.get("price_eur");

    let engineCm3 = null;
    if (needsCatalog) {
      const entry = selectedEngineEntry();
      const cm3 = volumeForEntry(entry);
      if (!entry || cm3 == null || !Number.isFinite(cm3) || cm3 <= 0) {
        renderResult({
          ok: false,
          error: "Выберите марку, модель и мотор из растаможка базы — объём подставится сам.",
        });
        return;
      }
      engineCm3 = Math.round(cm3);
      if (volumeInput) volumeInput.value = String(engineCm3);
    }

    const payload = {
      price_eur: needsPrice && rawPrice !== "" ? Number(rawPrice) : 0,
      age_band: age,
      vehicle_kind: kind,
      engine_cm3: engineCm3,
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
