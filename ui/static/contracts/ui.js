import { FINDINGS, KEEP_LIST } from "./lib/recommendations.js";
import { INVOICE_COMPLIANCE } from "./lib/invoice.js";
import { escapeHtml } from "./render.js";
import { formatDateTime } from "./lib/format.js";

const LEVELS = { critical: "Критично", important: "Важно", advice: "Имеет смысл" };

function field(label, name, data, extra = {}) {
  const value = data[name] ?? "";
  const wide = extra.wide ? " wide" : "";
  const hint = extra.hint ? `<span class="field-hint">${escapeHtml(extra.hint)}</span>` : "";
  let control;
  if (extra.type === "select") {
    control = `<select name="${name}">${extra.options
      .map(
        ([v, t]) =>
          `<option value="${escapeHtml(v)}" ${String(value) === v ? "selected" : ""}>${escapeHtml(t)}</option>`,
      )
      .join("")}</select>`;
  } else if (extra.type === "textarea") {
    control = `<textarea name="${name}" rows="${extra.rows || 3}">${escapeHtml(value)}</textarea>`;
  } else {
    control = `<input name="${name}" type="${extra.type || "text"}" value="${escapeHtml(value)}" placeholder="${escapeHtml(extra.placeholder || "")}" />`;
  }
  return `<label class="field${wide}"><span class="field-label">${escapeHtml(label)}</span>${control}${hint}</label>`;
}

function section(title, inner) {
  return `<section class="form-section"><h3>${escapeHtml(title)}</h3><div class="form-grid">${inner}</div></section>`;
}

function docKindLabel(kind) {
  if (kind === "commission") return "Комиссия";
  if (kind === "invoice") return "Счёт";
  return "Подбор ЕС";
}

function docKindSearch(kind) {
  if (kind === "commission") return "комиссия";
  if (kind === "invoice") return "счёт счет";
  return "подбор";
}

export function renderInvoiceForm(data) {
  const buyerFields =
    data.buyerType === "legal"
      ? [
          field("Наименование", "clientCompany", data, { wide: true, placeholder: "ООО «...»" }),
          field("УНП", "clientUnp", data, { hint: "Желательно для юрлица" }),
          field("Адрес", "clientAddress", data, { wide: true }),
        ]
      : [
          field("ФИО полностью", "clientName", data, {
            wide: true,
            placeholder: "Иванов Иван Иванович",
          }),
          field("Адрес", "clientAddress", data, { wide: true }),
        ];

  const itemFields =
    data.itemKind === "custom"
      ? [field("Наименование", "itemName", data, { wide: true, type: "textarea", rows: 3 })]
      : [
          field("Заголовок позиции", "itemName", data, {
            wide: true,
            placeholder: "Легковой автомобиль",
          }),
          field("Марка", "vehicleMake", data, { placeholder: "Mitsubishi" }),
          field("Модель", "vehicleModel", data, { placeholder: "Outlander" }),
          field("Год выпуска", "vehicleYear", data, { placeholder: "2014" }),
          field("VIN", "vehicleVin", data, { wide: true, placeholder: "Z8T…" }),
        ];

  const compliance = INVOICE_COMPLIANCE.map(
    (item) => `
      <li class="finding finding-${item.level}">
        <div class="finding-head">
          <span class="pill pill-${item.level}">${LEVELS[item.level]}</span>
          <h3>${escapeHtml(item.title)}</h3>
        </div>
        <dl>
          <div><dt>В образце</dt><dd>${escapeHtml(item.was)}</dd></div>
          <div><dt>Риск</dt><dd>${escapeHtml(item.risk)}</dd></div>
          <div><dt>В шаблоне</dt><dd>${escapeHtml(item.fix)}</dd></div>
        </dl>
      </li>`,
  ).join("");

  return `
    <form class="form" id="invoice-form">
      ${section(
        "Счёт",
        [
          field("Номер", "invoiceNumber", data, { placeholder: "01-150926" }),
          field("Дата", "invoiceDate", data, { type: "date" }),
          field("Срок оплаты, банк. дн.", "payDays", data),
        ].join(""),
      )}
      ${section(
        "Покупатель",
        [
          field("Тип", "buyerType", data, {
            type: "select",
            options: [
              ["individual", "Физическое лицо"],
              ["legal", "Юридическое лицо"],
            ],
          }),
          ...buyerFields,
          field("Телефон", "clientPhone", data, { placeholder: "+375 (29) 000-00-00" }),
          field("Email", "clientEmail", data),
        ].join(""),
      )}
      ${section(
        "Товар / услуга",
        [
          field("Тип позиции", "itemKind", data, {
            type: "select",
            options: [
              ["vehicle", "Автомобиль"],
              ["custom", "Свободное наименование"],
            ],
          }),
          ...itemFields,
          field("Количество", "itemQty", data),
          field("Цена / сумма, BYN", "amount", data, {
            placeholder: "30888.00",
            hint: "По умолчанию сумма с НДС 20 %",
          }),
          field("НДС", "vatMode", data, {
            type: "select",
            options: [
              ["included20", "20 % включён"],
              ["onTop20", "20 % сверх"],
              ["none", "Без НДС"],
            ],
          }),
          field("Назначение платежа", "purpose", data, {
            wide: true,
            placeholder: "Оплата по счёту … за автомобиль VIN …",
          }),
          field("Выдача авто (площадка)", "pickupAddress", data, {
            wide: true,
            placeholder: "г. Минск, ул. Максима Горецкого, 30",
          }),
        ].join(""),
      )}
      <details class="executor-details">
        <summary>Реквизиты продавца</summary>
        <div class="form-grid">
          ${field("Краткое наименование", "executorShort", data, { wide: true })}
          ${field("Полное", "executorName", data, { wide: true })}
          ${field("УНП", "executorUnp", data)}
          ${field("Юридический адрес", "executorAddress", data, {
            wide: true,
            hint: "В счетах — Скрыганова 6",
          })}
          ${field("Директор (подписи)", "executorDirectorShort", data)}
          ${field("Телефон", "executorPhone", data)}
          ${field("Email", "executorEmail", data)}
          ${field("Расчётный счёт", "executorAccount", data, { wide: true })}
          ${field("Банк", "executorBank", data, { wide: true })}
          ${field("SWIFT", "executorSwift", data)}
          ${field("УНП банка", "executorBankUnp", data)}
          ${field("ОКПО", "executorOkpo", data)}
        </div>
      </details>
      <details class="executor-details invoice-compliance">
        <summary>Проверка образца по законодательству РБ</summary>
        <ol class="findings findings-compact">${compliance}</ol>
        <p class="field-hint">Не юридическая консультация: перед массовым использованием сверьте режим НДС и адрес с бухгалтером/юристом.</p>
      </details>
    </form>`;
}

export function renderForm(data) {
  const clientFields =
    data.clientType === "legal"
      ? [
          field("Наименование", "clientCompany", data, { wide: true, placeholder: "ООО «...»" }),
          field("УНП", "clientUnp", data),
          field("Юридический адрес", "clientAddress", data, { wide: true }),
          field("Директор (именительный)", "clientDirector", data),
          field("Директор (родительный)", "clientDirectorGenitive", data, { hint: "в лице директора …" }),
          field("Основание полномочий", "clientBasis", data),
          field("Банковские реквизиты", "clientBankDetails", data, { wide: true }),
        ]
      : [
          field("Пол (для формулировок)", "gender", data, {
            type: "select",
            options: [
              ["male", "Мужской"],
              ["female", "Женский"],
            ],
          }),
          field("ФИО полностью", "clientName", data, {
            wide: true,
            hint: "Как в паспорте",
            placeholder: "Иванов Иван Иванович",
          }),
          field("Адрес регистрации", "clientAddress", data, { wide: true }),
          field("Паспорт", "passport", data, { placeholder: "BM1234567" }),
          field("Кем выдан", "passportIssuer", data),
          field("Дата выдачи", "passportDate", data, { type: "date" }),
          field("Идентификационный номер", "personalNumber", data),
        ];

  return `
    <form class="form" id="contract-form">
      ${section(
        "Договор",
        [
          field("Номер договора", "contractNumber", data, { placeholder: "П100926" }),
          field("Дата", "contractDate", data, { type: "date" }),
          field("Город", "city", data),
        ].join(""),
      )}
      ${section(
        "Заказчик",
        [
          field("Тип", "clientType", data, {
            type: "select",
            options: [
              ["individual", "Физическое лицо"],
              ["legal", "Юридическое лицо"],
            ],
          }),
          ...clientFields,
          field("Телефон", "clientPhone", data, { placeholder: "+375 (29) 000-00-00" }),
          field("Email", "clientEmail", data),
          field("Мессенджер", "clientMessenger", data),
        ].join(""),
      )}
      ${section(
        "Задание на подбор",
        [
          field("Марка", "vehicleMake", data, { placeholder: "Volkswagen" }),
          field("Модель", "vehicleModel", data, { placeholder: "Golf" }),
          field("Год от", "vehicleYearFrom", data, { placeholder: "2018" }),
          field("Год до", "vehicleYearTo", data, { placeholder: "2022" }),
          field("Максимальная цена лота", "vehicleBudget", data, { placeholder: "8500" }),
          field("Валюта лота", "vehicleBudgetCurrency", data, {
            type: "select",
            options: ["EUR", "USD", "BYN", "PLN"].map((c) => [c, c]),
          }),
          field("Площадки", "marketplace", data, { wide: true }),
          field("Иные пожелания", "vehicleNotes", data, {
            wide: true,
            placeholder: "без окраса, автомат, до 150 тыс. км",
          }),
        ].join(""),
      )}
      ${section(
        "Стоимость и сроки",
        [
          field("Вознаграждение, BYN", "amount", data),
          field("НДС", "vatMode", data, {
            type: "select",
            options: [
              ["none", "Не исчисляется"],
              ["included20", "20 % включён в сумму"],
              ["onTop20", "20 % сверх суммы"],
            ],
          }),
          field("Срок предоплаты, раб. дней", "prepaidDays", data),
          field("Оплата инвойса за лот, банк. дней", "invoicePayDays", data, {
            hint: "Критично для аукциона",
          }),
          field("Ответ по ставке до (Минск)", "bidReplyTime", data),
          field("Возврат при отказе до выигрыша, раб. дней", "refundDays", data),
          field("Срок на подпись акта, раб. дней", "actReviewDays", data),
          field("Неустойка за невыкуп, %", "penaltyPercent", data),
          `<label class="check wide"><input type="checkbox" name="photoConsent" ${data.photoConsent ? "checked" : ""} /><span>Клиент согласен на публикацию фото подобранного авто (без VIN и ФИО)</span></label>`,
        ].join(""),
      )}
      ${section(
        "Акт оказанных услуг",
        [
          field("Номер акта", "actNumber", data, {
            hint: "Пусто = номер договора + «-А»",
            placeholder: `${data.contractNumber || "П…"}-А`,
          }),
          field("Дата акта", "actDate", data, { type: "date" }),
          field("Период услуг с", "serviceFrom", data, { type: "date" }),
          field("Период услуг по", "serviceTo", data, { type: "date" }),
          field("Формулировка услуги в акте", "serviceDescription", data, {
            type: "textarea",
            wide: true,
          }),
        ].join(""),
      )}
      <details class="executor-details">
        <summary>Реквизиты Исполнителя</summary>
        <div class="form-grid">
          ${field("Полное наименование", "executorName", data, { wide: true })}
          ${field("Краткое", "executorShort", data)}
          ${field("УНП", "executorUnp", data)}
          ${field("Адрес", "executorAddress", data, { wide: true })}
          ${field("Директор", "executorDirector", data)}
          ${field("Директор в родительном", "executorDirectorGenitive", data)}
          ${field("Подпись (инициалы)", "executorDirectorShort", data)}
          ${field("Телефон", "executorPhone", data)}
          ${field("Email", "executorEmail", data)}
          ${field("Расчётный счёт", "executorAccount", data)}
          ${field("Банк", "executorBank", data, { wide: true })}
          ${field("SWIFT", "executorSwift", data)}
          ${field("УНП банка", "executorBankUnp", data)}
          ${field("ОКПО", "executorOkpo", data)}
        </div>
      </details>
    </form>`;
}

export function renderAnalysis() {
  const findings = FINDINGS.map(
    (item, i) => `
      <li class="finding finding-${item.level}">
        <div class="finding-head">
          <span class="finding-num">${String(i + 1).padStart(2, "0")}</span>
          <span class="pill pill-${item.level}">${LEVELS[item.level]}</span>
          <h3>${escapeHtml(item.title)}</h3>
        </div>
        <dl>
          <div><dt>Как было</dt><dd>${escapeHtml(item.was)}</dd></div>
          <div><dt>Риск</dt><dd>${escapeHtml(item.risk)}</dd></div>
          <div><dt>Как в шаблоне</dt><dd>${escapeHtml(item.fix)}</dd></div>
        </dl>
      </li>`,
  ).join("");

  return `
    <div class="analysis">
      <header class="analysis-hero">
        <p class="eyebrow">Разбор образца · подбор ЕС</p>
        <h2>Что в текущем договоре ломается и что мы поправили</h2>
        <p>Образец рабочий как коммерческий щит: «мы не продавцы автомобиля». Юридически он смешанный, с дырами в сроках, учёте и потребительском праве. Ниже — конкретные правки, уже заложенные в новый шаблон.</p>
      </header>
      <section class="keep">
        <h3>Что оставляем</h3>
        <ul>${KEEP_LIST.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </section>
      <ol class="findings">${findings}</ol>
      <aside class="disclaimer">Шаблон подготовлен как рабочий проект документов под законодательством Республики Беларусь. Перед массовым использованием его стоит показать вашему юристу и бухгалтеру: режим НДС, учётная политика и фактическая схема расчётов с площадками могут требовать точечной подстройки.</aside>
    </div>`;
}

export function renderArchive({ rows = [], query = "", error = "" } = {}) {
  const filtered = rows.filter((row) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    const kind = docKindSearch(row.doc_kind);
    return `${row.contract_number || ""} ${row.client_name || ""} ${row.created_by || ""} ${kind}`
      .toLowerCase()
      .includes(q);
  });
  const body = filtered.length
    ? filtered
        .map((row) => {
          const label = docKindLabel(row.doc_kind);
          return `
        <tr data-action="open" data-id="${escapeHtml(row.id)}">
          <td>${escapeHtml(row.contract_number || "—")}</td>
          <td>${escapeHtml(label)}</td>
          <td>${escapeHtml(row.client_name || "Без клиента")}</td>
          <td>${escapeHtml(row.amount ? `${row.amount} BYN` : "—")}</td>
          <td>${escapeHtml(row.created_by || "—")}</td>
          <td>${escapeHtml(formatDateTime(row.updated_at))}</td>
          <td class="archive-actions">
            <button type="button" data-action="delete" data-id="${escapeHtml(row.id)}">Удалить</button>
          </td>
        </tr>`;
        })
        .join("")
    : `<tr><td colspan="7" class="archive-empty">${
        rows.length
          ? "Ничего не найдено."
          : "Архив пуст. Создайте первый договор — он появится у всех администраторов."
      }</td></tr>`;

  return `
    <div class="archive">
      <div class="archive-bar">
        <input name="search" value="${escapeHtml(query)}" placeholder="Поиск по клиенту, номеру или пользователю" data-action="search" />
        <button type="button" class="primary" data-action="new">Новый подбор</button>
        <button type="button" class="ghost" data-action="new-commission">Новая комиссия</button>
        <button type="button" class="ghost" data-action="new-invoice">Новый счёт</button>
      </div>
      ${error ? `<p class="gate-error">${escapeHtml(error)}</p>` : ""}
      <table class="archive-table">
        <thead>
          <tr>
            <th>Номер</th>
            <th>Тип</th>
            <th>Клиент</th>
            <th>Сумма</th>
            <th>Пользователь</th>
            <th>Изменён</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}
