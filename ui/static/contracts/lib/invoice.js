import { suggestInvoiceNumber, todayIso, formatDateLong, dash } from "./format.js";
import { formatAmount, moneyToWords, computeVat, parseMoney } from "./money.js";

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
    level: "critical",
    title: "«Без НДС» без основания",
    was: "В графе НДС указано «Без НДС» без ссылки на норму/режим.",
    risk: "При проверке могут потребовать, почему НДС не выделен (УСН, освобождение и т.п.). Формулировка без основания выглядит как недооформление.",
    fix: "Поле «Основание без НДС» + вывод строки под итогом.",
  },
  {
    level: "important",
    title: "Юридический адрес продавца",
    was: "В образце: ул. Скрыганова, 6. На сайте и в company_info — ул. М. Горецкого, 30.",
    risk: "Расхождение реквизитов в платёжных документах и ЕГР / договорах.",
    fix: "В генераторе подставляется актуальный адрес из реквизитов компании на сайте.",
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
    vatMode: "none",
    vatBasis: "НДС не исчисляется (уточните режим налогообложения у бухгалтера)",
    currencyNote: "BYN",

    purpose: "",
    payDays: "3",

    executorName: ex.executorName || "Общество с ограниченной ответственностью «Сканди Моторс»",
    executorShort: ex.executorShort || "ООО «Сканди Моторс»",
    executorUnp: ex.executorUnp || "193866357",
    executorAddress: ex.executorAddress || "г. Минск, ул. Максима Горецкого, 30",
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
  const vat = computeVat(d.amount, d.vatMode);
  const qty = Math.max(1, parseInt(String(d.itemQty || "1"), 10) || 1);
  const unitGross = vat.gross;
  const lineGross = Math.round(unitGross * qty * 100) / 100;
  const unitNet = vat.net;
  const unitVat = vat.vat;
  const vatCell = d.vatMode === "none" ? "Без НДС" : formatAmount(unitVat);
  const priceCell = formatAmount(d.vatMode === "onTop20" ? unitNet : unitGross);
  const priceWithVatCell = formatAmount(unitGross);
  const totalCell = formatAmount(lineGross);
  const totalWords = moneyToWords(lineGross);
  const dateLong = formatDateLong(d.invoiceDate)
    .replace(/^«/, "")
    .replace(/» /, " ")
    .replace(/ г\.$/, "г.");

  const sellerHeader = [
    d.executorShort || d.executorName,
    `Юридический адрес: ${d.executorAddress}`,
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
  ];

  if (d.vatMode === "none" && String(d.vatBasis || "").trim()) {
    blocks.push({ type: "note", text: String(d.vatBasis).trim() });
  } else if (d.vatMode !== "none") {
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
  const vat = computeVat(total, d.vatMode);
  const gross = Math.round(vat.gross * qty * 100) / 100;
  return gross ? `${formatAmount(gross)} BYN` : "—";
}
