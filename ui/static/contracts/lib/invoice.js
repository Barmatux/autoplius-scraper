import { suggestInvoiceNumber, todayIso, formatDateLong, dash } from "./format.js";
import { computeVat, parseMoney, invoiceMoneyWords } from "./money.js";

/** Юр. адрес в счетах (не путать с площадкой выдачи). */
export const INVOICE_LEGAL_ADDRESS = "г. Минск, ул. Скрыганова, дом 6, помещение 7.";
/** Площадка выдачи автомобиля. */
export const INVOICE_PICKUP_ADDRESS = "г. Минск, ул. Максима Горецкого, 30";

const LOGO_URL = "/static/contracts/invoice/logo.png";

const CDN = [
  "https://unpkg.com/pizzip@3.1.6/dist/pizzip.js",
  "https://unpkg.com/docxtemplater@3.50.0/build/docxtemplater.js",
  "https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js",
];

let libsPromise = null;
let tplB64 = null;

function executorFromPage() {
  const raw = typeof window !== "undefined" ? window.__CONTRACT_DEFAULTS__ : null;
  return raw && typeof raw === "object" ? raw : {};
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if ([...document.scripts].some((s) => s.src === src)) {
      resolve();
      return;
    }
    const el = document.createElement("script");
    el.src = src;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error("Не удалось загрузить " + src));
    document.head.appendChild(el);
  });
}

async function ensureLibs() {
  if (!libsPromise) {
    libsPromise = CDN.reduce((p, src) => p.then(() => loadScript(src)), Promise.resolve());
  }
  await libsPromise;
}

async function ensureTemplate() {
  if (tplB64) return tplB64;
  const text = await fetch("/static/contracts/invoice/schet_tpl.b64").then((r) => r.text());
  tplB64 = text.trim();
  return tplB64;
}

/** 30888,00 like the paper sample (no thousands separator). */
export function formatInvoiceAmount(value) {
  const { total } = parseMoney(value);
  return total.toFixed(2).replace(".", ",");
}

/** «… белорусских рублей ноль копеек» as in the sample. */
export function invoiceTotalWords(value) {
  return invoiceMoneyWords(value);
}

export const INVOICE_COMPLIANCE = [
  {
    level: "critical",
    title: "Покупатель",
    was: "В образце поле пустое.",
    risk: "Счёт без плательщика плохо стыкуется с оплатой.",
    fix: "Заполняйте покупателя в форме.",
  },
  {
    level: "important",
    title: "НДС",
    was: "Авто — без НДС; услуги — НДС 20 %.",
    risk: "Неверная графа НДС в счёте.",
    fix: "Для автомобиля по умолчанию «Без НДС»; для услуги — 20 %.",
  },
  {
    level: "important",
    title: "Адреса",
    was: "Юр. адрес Скрыганова 6; выдача — Горецкого 30.",
    risk: "Клиент путает площадку и юр. адрес.",
    fix: "В шаблоне разделены юр. адрес и строка про выдачу с площадки.",
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
    // Авто — без НДС; для услуги форма переключит на included20.
    vatMode: "none",
    currencyNote: "BYN",

    purpose: "",
    payDays: "3",
    pickupAddress: INVOICE_PICKUP_ADDRESS,

    executorName: ex.executorName || "Общество с ограниченной ответственностью «Сканди Моторс»",
    executorShort: ex.executorShort || "ООО «Сканди Моторс»",
    executorUnp: ex.executorUnp || "193866357",
    executorAddress: INVOICE_LEGAL_ADDRESS,
    executorEmail: ex.executorEmail || "scandimotorsby@gmail.com",
    executorPhone: ex.executorPhone || "+375336987799",
    executorDirector: ex.executorDirector || "Герасимец Максим Сергеевич",
    executorDirectorShort: ex.executorDirectorShort || "Герасимец М.С.",
    executorAccount: ex.executorAccount || "BY58 ALFA 3012 2G91 3900 1027 0000",
    executorBank: ex.executorBank || "ЗАО «АЛЬФА-БАНК». 220013 Минск, ул. Сурганова, 43-47.",
    executorSwift: ex.executorSwift || "ALFABY2X",
    executorBankUnp: ex.executorBankUnp || "101541947",
    executorOkpo: ex.executorOkpo || "37526626",
  };
}

function resolveVatMode(d) {
  if (d.vatMode) return d.vatMode;
  return d.itemKind === "custom" ? "included20" : "none";
}

function itemNameMultiline(d) {
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
    return [
      dash(d.clientCompany, "________________"),
      d.clientUnp ? `УНП ${d.clientUnp}` : "",
      d.clientAddress ? `адрес: ${d.clientAddress}` : "",
      d.clientPhone || "",
    ]
      .filter(Boolean)
      .join(", ");
  }
  return [
    dash(d.clientName, "________________"),
    d.clientAddress ? `адрес: ${d.clientAddress}` : "",
    d.clientPhone || "",
  ]
    .filter(Boolean)
    .join(", ");
}

function phoneCompact(phone) {
  return String(phone || "").replace(/[\s()-]/g, "");
}

function invoiceDateLong(iso) {
  return formatDateLong(iso)
    .replace(/^«/, "")
    .replace(/» /, " ")
    .replace(/ г\.$/, "г.");
}

function amounts(d) {
  const vatMode = resolveVatMode(d);
  const vat = computeVat(d.amount, vatMode);
  const qty = Math.max(1, parseInt(String(d.itemQty || "1"), 10) || 1);
  const unitGross = vat.gross;
  const lineGross = Math.round(unitGross * qty * 100) / 100;
  const unitNet = vat.net;
  const unitVat = vat.vat;
  return {
    vatMode,
    qty,
    unitNet,
    unitVat,
    unitGross,
    lineGross,
    price: formatInvoiceAmount(vatMode === "none" ? unitGross : unitNet),
    vatCell: vatMode === "none" ? "Без НДС" : formatInvoiceAmount(unitVat),
    priceVat: formatInvoiceAmount(unitGross),
    total: formatInvoiceAmount(lineGross),
    totalWords: invoiceTotalWords(lineGross),
  };
}

export function buildInvoice(d) {
  const a = amounts(d);
  const legalAddress = INVOICE_LEGAL_ADDRESS;
  const pickupAddress = String(d.pickupAddress || "").trim() || INVOICE_PICKUP_ADDRESS;
  const payDays = d.payDays || "3";

  return {
    kind: "invoice",
    logoUrl: LOGO_URL,
    companyShort: d.executorShort || "ООО «Сканди Моторс»",
    legalAddress,
    unp: d.executorUnp || "193866357",
    phone: phoneCompact(d.executorPhone),
    email: d.executorEmail || "",
    account: d.executorAccount || "",
    bank: d.executorBank || "",
    swift: d.executorSwift || "ALFABY2X",
    bankUnp: d.executorBankUnp || "",
    okpo: d.executorOkpo || "",
    title: `Счет № ${dash(d.invoiceNumber, "____")} от ${invoiceDateLong(d.invoiceDate)}`,
    buyer: buyerLine(d),
    itemName: itemNameMultiline(d),
    qty: String(a.qty),
    price: a.price,
    vatCell: a.vatCell,
    priceVat: a.priceVat,
    total: a.total,
    totalWords: a.totalWords,
    payNote: `Счёт действителен / оплатить в течение ${payDays} банк. дн. с даты выставления (если иное не согласовано договором).`,
    pickupNote: `Автомобиль забирать с площадки по адресу: ${pickupAddress}.`,
    directorShort: d.executorDirectorShort || "Герасимец М.С.",
    amountGross: a.lineGross,
  };
}

export function invoiceAmountLabel(d) {
  const a = amounts(d);
  return a.lineGross ? `${a.total} BYN` : "—";
}

function b64ToUint8(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

export async function downloadInvoiceDocx(data, filename) {
  await ensureLibs();
  const b64 = await ensureTemplate();
  const doc = buildInvoice(data);
  const PizZip = window.PizZip;
  const Docxtemplater = window.Docxtemplater;
  const saveAs = window.saveAs;
  if (!PizZip || !Docxtemplater || !saveAs) {
    throw new Error("Библиотеки Word не загрузились.");
  }
  const zip = new PizZip(b64ToUint8(b64));
  const templater = new Docxtemplater(zip, {
    paragraphLoop: true,
    linebreaks: true,
    delimiters: { start: "{{", end: "}}" },
  });
  templater.render({
    company_short: doc.companyShort,
    legal_address: doc.legalAddress,
    unp: doc.unp,
    phone: doc.phone,
    email: doc.email,
    account: doc.account,
    bank: doc.bank,
    swift: doc.swift,
    bank_unp: doc.bankUnp,
    okpo: doc.okpo,
    invoice_number: dash(data.invoiceNumber, "____"),
    invoice_date: invoiceDateLong(data.invoiceDate),
    buyer: doc.buyer,
    item_name: doc.itemName,
    qty: doc.qty,
    price: doc.price,
    vat_cell: doc.vatCell,
    price_vat: doc.priceVat,
    total: doc.total,
    total_fmt: doc.total,
    total_words: doc.totalWords,
    pay_note: doc.payNote,
    pickup_note: doc.pickupNote,
    director_short: doc.directorShort,
  });
  const out = templater.getZip().generate({
    type: "blob",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });
  const name = filename.endsWith(".docx") ? filename : `${filename}.docx`;
  saveAs(out, name);
}
