import { suggestInvoiceNumber, todayIso, formatDateLong, dash } from "./format.js";
import { formatAmount, moneyToWords, computeVat, parseMoney } from "./money.js";

/** Юр. адрес в счетах (ЕГР / реквизиты для оплаты). */
export const INVOICE_LEGAL_ADDRESS = "г. Минск, ул. Скрыганова, дом 6, помещение 7";
/** Площадка выдачи автомобиля. */
export const INVOICE_PICKUP_ADDRESS = "г. Минск, ул. Максима Горецкого, 30";

function executorFromPage() {
  const raw = typeof window !== "undefined" ? window.__CONTRACT_DEFAULTS__ : null;
  return raw && typeof raw === "object" ? raw : {};
}

export const INVOICE_COMPLIANCE = [
  {
    level: "critical",
    title: "Покупатель не заполнен",
    was: "В образце поле «Покупатель» пустое.",
    risk: "Счёт без идентификации плательщика слабо связывает платёж с договором/авто и усложняет учёт и претензии. Для юрлица желательны наименование и УНП.",
    fix: "Обязательные поля покупателя в форме; для юрлица — УНП.",
  },
  {
    level: "important",
    title: "НДС 20 %",
    was: "В образце стояло «Без НДС».",
    risk: "При работе с НДС сумма и графа НДС должны быть согласованы.",
    fix: "По умолчанию НДС 20 % включён в стоимость; в таблице выводятся цена без НДС, сумма НДС и цена с НДС.",
  },
  {
    level: "important",
    title: "Юридический адрес и выдача",
    was: "В образце только Скрыганова 6.",
    risk: "Клиент может приехать не на ту площадку.",
    fix: "В реквизитах — Скрыганова 6; отдельно указано, что авто забирать с Горецкого 30.",
  },
  {
    level: "advice",
    title: "Статус счёта в РБ",
    was: "Счёт оформлен как коммерческий запрос на оплату.",
    risk: "Счёт на оплату в РБ не имеет жёсткой обязательной формы первички; это оферта/требование об оплате. Для учёта первичка — договор, ТТН/акт, платёжка.",
    fix: "Шаблон сохраняет структуру образца и усиливает идентификацию сторон и НДС.",
  },
  {
    level: "advice",
    title: "Описание товара",
    was: "Марка, год, VIN — достаточно для легкового авто.",
    risk: "Низкий, если VIN и год совпадают с договором/ПТС.",
    fix: "Поля марки/модели/года/VIN в форме; при услуге — свободное наименование.",
  },
];

export function createInvoiceDefaultData() {
  const date = todayIso();
  const ex = executorFromPage();
  return {
    docType: "invoice",
    invoiceNumber: suggestInvoiceNumber(date),
    invoiceDate: date,

    buyerType: "individual",
    clientName: "",
    clientCompany: "",
    clientUnp: "",
    clientAddress: "",
    clientPhone: "",
    clientEmail: "",

    itemKind: "vehicle",
    itemName: "Легковой автомобиль",
    vehicleMake: "",
    vehicleModel: "",
    vehicleYear: "",
    vehicleVin: "",
    itemQty: "1",
    amount: "",
    vatMode: "included20",
    currencyNote: "BYN",

    purpose: "",
    payDays: "3",
    pickupAddress: INVOICE_PICKUP_ADDRESS,

    executorName: ex.executorName || "Общество с ограниченной ответственностью «Сканди Моторс»",
    executorShort: ex.executorShort || "ООО «Сканди Моторс»",
    executorUnp: ex.executorUnp || "193866357",
    executorAddress: INVOICE_LEGAL_ADDRESS,
    executorEmail: ex.executorEmail || "scandimotorsby@gmail.com",
    executorPhone: ex.executorPhone || "+375 (33) 698-77-99",
    executorDirector: ex.executorDirector || "Герасимец Максим Сергеевич",
    executorDirectorShort: ex.executorDirectorShort || "Герасимец М.С.",
    executorAccount: ex.executorAccount || "BY58 ALFA 3012 2G91 3900 1027 0000",
    executorBank: ex.executorBank || "ЗАО «Альфа-Банк», 220013, г. Минск, ул. Сурганова, 43-47",
    executorSwift: ex.executorSwift || "ALFABY2X",
    executorBankUnp: ex.executorBankUnp || "101541947",
    executorOkpo: ex.executorOkpo || "37526626",
  };
}

function itemDescription(d) {
  if (d.itemKind === "custom") {
    return String(d.itemName || "").trim() || "________________";
  }
  const lines = [String(d.itemName || "Легковой автомобиль").trim()];
  const makeModel = [d.vehicleMake, d.vehicleModel].filter(Boolean).join(" ").trim();
  const year = String(d.vehicleYear || "").trim();
  if (makeModel || year) {
    lines.push([makeModel, year ? `${year} г.в.` : ""].filter(Boolean).join(" "));
  }
  const vin = String(d.vehicleVin || "").trim();
  if (vin) lines.push(`VIN ${vin}`);
  return lines.filter(Boolean).join("\n");
}

function buyerLine(d) {
  if (d.buyerType === "legal") {
    const parts = [
      dash(d.clientCompany, "________________"),
      d.clientUnp ? `УНП ${d.clientUnp}` : "",
      d.clientAddress ? `адрес: ${d.clientAddress}` : "",
      d.clientPhone || "",
    ].filter(Boolean);
    return parts.join(", ");
  }
  const parts = [
    dash(d.clientName, "________________"),
    d.clientAddress ? `адрес: ${d.clientAddress}` : "",
    d.clientPhone || "",
  ].filter(Boolean);
  return parts.join(", ");
}

export function buildInvoice(d) {
  const vat = computeVat(d.amount, d.vatMode || "included20");
  const qty = Math.max(1, parseInt(String(d.itemQty || "1"), 10) || 1);
  const unitGross = vat.gross;
  const lineGross = Math.round(unitGross * qty * 100) / 100;
  const unitNet = vat.net;
  const unitVat = vat.vat;
  const vatMode = d.vatMode || "included20";
  const vatCell = vatMode === "none" ? "Без НДС" : formatAmount(unitVat);
  const priceCell = formatAmount(vatMode === "none" ? unitGross : unitNet);
  const priceWithVatCell = formatAmount(unitGross);
  const totalCell = formatAmount(lineGross);
  const totalWords = moneyToWords(lineGross);
  const dateLong = formatDateLong(d.invoiceDate)
    .replace(/^«/, "")
    .replace(/» /, " ")
    .replace(/ г\.$/, "г.");

  const legalAddress = String(d.executorAddress || "").trim() || INVOICE_LEGAL_ADDRESS;
  const pickupAddress = String(d.pickupAddress || "").trim() || INVOICE_PICKUP_ADDRESS;

  const sellerHeader = [
    d.executorShort || d.executorName,
    `Юридический адрес: ${legalAddress}`,
    `УНП: ${d.executorUnp}`,
    `Тел (Viber / WhatsApp / Telegram): ${String(d.executorPhone || "").replace(/\s/g, "")}`,
    d.executorEmail,
    "Банковские реквизиты:",
    `Р/c ${d.executorAccount} в ${d.currencyNote || "BYN"}`,
    d.executorBank,
    `СВИФТ - ${d.executorSwift}, УНП ${d.executorBankUnp}, ОКПО ${d.executorOkpo}.`,
  ].filter((line) => line != null && String(line).trim() !== "");

  const blocks = [
    {
      type: "table",
      invoice: true,
      columns: [
        "№",
        "Наименование товара, услуги",
        "Кол-во",
        "Цена, руб. коп.",
        "НДС , руб. коп.",
        "Цена с НДС, руб. коп.",
        "Всего к оплате, руб. коп.",
      ],
      rows: [
        [
          "1",
          itemDescription(d),
          String(qty),
          priceCell,
          vatCell,
          priceWithVatCell,
          totalCell,
        ],
      ],
    },
    {
      type: "p",
      text: `Итого к оплате: ${totalCell} руб. (${totalWords}).`,
    },
    {
      type: "note",
      text: `Автомобиль забирать с площадки по адресу: ${pickupAddress}.`,
    },
  ];

  if (vatMode !== "none") {
    blocks.push({ type: "note", text: vat.label });
  }

  if (String(d.purpose || "").trim()) {
    blocks.push({ type: "note", text: `Назначение платежа: ${String(d.purpose).trim()}` });
  }
  if (d.payDays) {
    blocks.push({
      type: "note",
      text: `Счёт действителен / оплатить в течение ${d.payDays} банк. дн. с даты выставления (если иное не согласовано договором).`,
    });
  }

  return {
    kind: "invoice",
    clientType: "legal",
    kicker: "",
    title: `Счет № ${dash(d.invoiceNumber, "____")} от ${dateLong}`,
    subtitle: [],
    meta: { city: "", date: "" },
    preamble: "",
    sellerHeader,
    buyer: buyerLine(d),
    blocks,
    signatures: {
      leftTitle: "",
      leftLines: [],
      leftRole: "",
      leftSign: "",
      rightTitle: "",
      rightLines: [],
      rightRole: "",
      rightSign: `___________________ Директор ${d.executorDirectorShort || ""}`.trim(),
    },
    amountGross: lineGross,
  };
}

export function invoiceAmountLabel(d) {
  const { total } = parseMoney(d.amount);
  const qty = Math.max(1, parseInt(String(d.itemQty || "1"), 10) || 1);
  const vat = computeVat(total, d.vatMode || "included20");
  const gross = Math.round(vat.gross * qty * 100) / 100;
  return gross ? `${formatAmount(gross)} BYN` : "—";
}
