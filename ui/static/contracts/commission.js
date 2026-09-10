/**
 * Commission contract form (Scandi Motors blank) mounted into contracts admin UI.
 */
import {
  createContract,
  updateContract,
} from "../lib/api.js";

const ALL_FIELDS = [
  "komitent_fio",
  "komitent_sex",
  "komitent_phone",
  "komitent_addr",
  "komitent_passport",
  "komitent_passport_issued",
  "komitent_id",
  "komitent_account",
  "komitent_bank",
  "komitent_bic",
  "car_vin",
  "car_make_model",
  "car_year",
  "car_plate",
  "car_sts",
  "car_engine",
  "car_gearbox",
  "car_drive",
  "car_color",
  "car_type",
  "car_keys",
  "car_mileage",
  "dog_date",
  "dog_num",
  "akt_num",
  "price_num",
  "fee_num",
  "fuel_level",
  "has_service_book",
  "has_spare",
  "has_jack",
  "has_wrench",
  "has_firstaid",
  "has_ext",
  "has_sign",
  "lkp_measured",
  "diag_done",
  "defects",
  "commission_member_1",
];

const CDN = [
  "https://unpkg.com/pizzip@3.1.6/dist/pizzip.js",
  "https://unpkg.com/docxtemplater@3.50.0/build/docxtemplater.js",
  "https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js",
];

let libsPromise = null;
let formHtmlCache = null;
let dogTpl = null;
let aktTpl = null;

function $(id) {
  return document.getElementById(id);
}

function pad(n) {
  return n < 10 ? "0" + n : "" + n;
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

async function ensureTemplates() {
  if (dogTpl && aktTpl) return;
  const base = "/static/contracts/commission/";
  const [dog, akt] = await Promise.all([
    fetch(base + "dog_tpl.b64").then((r) => r.text()),
    fetch(base + "akt_tpl.b64").then((r) => r.text()),
  ]);
  dogTpl = dog.trim();
  aktTpl = akt.trim();
}

async function ensureFormHtml() {
  if (formHtmlCache) return formHtmlCache;
  const html = await fetch("/static/contracts/commission/form.html").then((r) => r.text());
  formHtmlCache = html.replace(/<!-- Внешние библиотеки -->[\s\S]*$/, "").trim();
  return formHtmlCache;
}

function dateStrFull(iso) {
  if (!iso) return "";
  const months = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
  ];
  const [y, m, d] = iso.split("-");
  return `${parseInt(d, 10).toString().padStart(2, "0")} ${months[+m - 1]} ${y} г.`;
}

function dogNumFromDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `001-${pad(+d)}${pad(+m)}${y.slice(-2)}`;
}

function plural(n, one, few, many) {
  n = Math.abs(n) % 100;
  const n1 = n % 10;
  if (n > 10 && n < 20) return many;
  if (n1 > 1 && n1 < 5) return few;
  if (n1 === 1) return one;
  return many;
}

const _u = [
  "",
  "один",
  "два",
  "три",
  "четыре",
  "пять",
  "шесть",
  "семь",
  "восемь",
  "девять",
  "десять",
  "одиннадцать",
  "двенадцать",
  "тринадцать",
  "четырнадцать",
  "пятнадцать",
  "шестнадцать",
  "семнадцать",
  "восемнадцать",
  "девятнадцать",
];
const _uF = [
  "",
  "одна",
  "две",
  "три",
  "четыре",
  "пять",
  "шесть",
  "семь",
  "восемь",
  "девять",
  "десять",
  "одиннадцать",
  "двенадцать",
  "тринадцать",
  "четырнадцать",
  "пятнадцать",
  "шестнадцать",
  "семнадцать",
  "восемнадцать",
  "девятнадцать",
];
const _t = [
  "",
  "",
  "двадцать",
  "тридцать",
  "сорок",
  "пятьдесят",
  "шестьдесят",
  "семьдесят",
  "восемьдесят",
  "девяносто",
];
const _h = [
  "",
  "сто",
  "двести",
  "триста",
  "четыреста",
  "пятьсот",
  "шестьсот",
  "семьсот",
  "восемьсот",
  "девятьсот",
];

function under1000(n, gender) {
  const out = [];
  out.push(_h[Math.floor(n / 100)]);
  const rem = n % 100;
  if (rem < 20) {
    out.push((gender === "f" ? _uF : _u)[rem]);
  } else {
    out.push(_t[Math.floor(rem / 10)]);
    out.push((gender === "f" ? _uF : _u)[rem % 10]);
  }
  return out.filter(Boolean).join(" ");
}

function numToWords(n, gender) {
  if (n === 0) return "ноль";
  const parts = [];
  const groups = [
    { div: 1000000000, gender: "m", forms: ["миллиард", "миллиарда", "миллиардов"] },
    { div: 1000000, gender: "m", forms: ["миллион", "миллиона", "миллионов"] },
    { div: 1000, gender: "f", forms: ["тысяча", "тысячи", "тысяч"] },
    { div: 1, gender, forms: null },
  ];
  let rest = n;
  for (const g of groups) {
    const v = Math.floor(rest / g.div);
    rest = rest % g.div;
    if (v > 0) {
      parts.push(under1000(v, g.gender));
      if (g.forms) parts.push(plural(v, ...g.forms));
    }
  }
  return parts.join(" ").replace(/\s+/g, " ").trim();
}

function rublesToWords(amount) {
  amount = Math.round(amount * 100) / 100;
  const rub = Math.floor(amount);
  const kop = Math.round((amount - rub) * 100);
  return `${numToWords(rub, "m")} ${plural(rub, "белорусский рубль", "белорусских рубля", "белорусских рублей")} ${pad(kop)} ${plural(kop, "копейка", "копейки", "копеек")}`;
}

function isValidVIN(vin) {
  vin = (vin || "").toUpperCase();
  if (vin.length !== 17) return false;
  if (/[IOQ]/.test(vin)) return false;
  if (!/^[A-HJ-NPR-Z0-9]+$/.test(vin)) return false;
  return true;
}

function formatMoney(n) {
  return (Math.round(n * 100) / 100).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatNumber(n) {
  const v = parseInt(n, 10);
  if (!v && v !== 0) return "";
  return v.toLocaleString("ru-RU");
}

function makeShortFio(full) {
  const parts = (full || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0];
  const initials = parts
    .slice(1)
    .map((p) => (p[0] ? p[0].toUpperCase() + "." : ""))
    .join("");
  return `${parts[0]} ${initials}`.trim();
}

function readForm() {
  const obj = { docType: "commission" };
  ALL_FIELDS.forEach((id) => {
    const el = $(id);
    if (!el) return;
    obj[id] = el.type === "checkbox" ? el.checked : el.value;
  });
  return obj;
}

function writeForm(obj = {}) {
  ALL_FIELDS.forEach((id) => {
    if (obj[id] === undefined) return;
    const el = $(id);
    if (!el) return;
    if (el.type === "checkbox") el.checked = !!obj[id];
    else el.value = obj[id];
  });
}

function buildContext() {
  const sex = $("komitent_sex").value;
  const ending = sex === "f" ? "ая" : "ый";
  const fioFull = $("komitent_fio").value.trim();
  const fioShort = makeShortFio(fioFull);
  const dogDate = dateStrFull($("dog_date").value);
  const dogNum = $("dog_num").value || dogNumFromDate($("dog_date").value);
  const aktNum = $("akt_num").value || "А" + dogNum;
  const dogYear = $("dog_date").value ? $("dog_date").value.split("-")[0] : "";
  let dogEndDate = "";
  if ($("dog_date").value) {
    const [yy, mm, dd] = $("dog_date").value.split("-").map((n) => parseInt(n, 10));
    dogEndDate = dateStrFull(`${yy + 1}-${pad(mm)}-${pad(dd)}`);
  }
  const price = parseFloat($("price_num").value) || 0;
  const fee = parseFloat($("fee_num").value) || 0;
  const yn = (el) => ($(el).checked ? "да" : "нет");
  return {
    DOG_NUM: dogNum,
    DOG_DATE: dogDate,
    DOG_YEAR: dogYear,
    DOG_END_DATE: dogEndDate,
    AKT_NUM: aktNum,
    KOMITENT_FIO_FULL: fioFull,
    KOMITENT_FIO_SHORT: fioShort,
    KOMITENT_END_YJ: ending,
    KOMITENT_ADDR: $("komitent_addr").value,
    KOMITENT_PASSPORT: $("komitent_passport").value,
    KOMITENT_PASSPORT_ISSUED: $("komitent_passport_issued").value,
    KOMITENT_ID: $("komitent_id").value,
    KOMITENT_PHONE: $("komitent_phone").value,
    KOMITENT_ACCOUNT: $("komitent_account").value,
    KOMITENT_BANK: $("komitent_bank").value,
    KOMITENT_BIC: $("komitent_bic").value,
    HAS_BANK: !!(
      $("komitent_account").value.trim() ||
      $("komitent_bank").value.trim() ||
      $("komitent_bic").value.trim()
    ),
    CAR_MAKE_MODEL: $("car_make_model").value.toUpperCase(),
    CAR_VIN: $("car_vin").value.toUpperCase(),
    CAR_YEAR: $("car_year").value,
    CAR_STS: $("car_sts").value,
    CAR_PLATE: $("car_plate").value,
    CAR_ENGINE: $("car_engine").value,
    CAR_GEARBOX: $("car_gearbox").value,
    CAR_DRIVE: $("car_drive").value,
    CAR_COLOR: $("car_color").value,
    CAR_TYPE: $("car_type").value,
    CAR_KEYS: $("car_keys").value,
    CAR_MILEAGE: formatNumber($("car_mileage").value),
    PRICE_NUM: formatMoney(price),
    PRICE_WORDS: price > 0 ? rublesToWords(price) : "",
    FEE_NUM: formatMoney(fee),
    FEE_WORDS: fee > 0 ? rublesToWords(fee) : "",
    HAS_SERVICE_BOOK: yn("has_service_book"),
    HAS_SPARE: yn("has_spare"),
    HAS_JACK: yn("has_jack"),
    HAS_WRENCH: yn("has_wrench"),
    HAS_FIRSTAID: yn("has_firstaid"),
    HAS_EXT: yn("has_ext"),
    HAS_SIGN: yn("has_sign"),
    COMMISSION_MEMBER_1: $("commission_member_1").value,
    LKP_MEASURED: $("lkp_measured").value,
    DIAG_DONE: $("diag_done").value,
    DEFECTS:
      $("defects").value ||
      "Видимых дефектов кузова и салона, кроме нормального эксплуатационного износа, не выявлено.",
    FUEL_LEVEL: $("fuel_level").value || "не указан",
  };
}

function buildDocxBlob(b64, data) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const zip = new PizZip(bytes);
  const Docxtemplater = window.docxtemplater;
  const doc = new Docxtemplater(zip, {
    paragraphLoop: true,
    linebreaks: true,
    nullGetter: () => "",
  });
  doc.render(data);
  return doc.getZip().generate({
    type: "blob",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });
}

function refreshPreviews() {
  const iso = $("dog_date")?.value;
  if (!iso) return;
  if ($("dog_num_preview")) $("dog_num_preview").textContent = "№ договора: " + dogNumFromDate(iso);
  if ($("dog_num") && !$("dog_num").value) $("dog_num").value = dogNumFromDate(iso);
  if ($("akt_num") && !$("akt_num").value) $("akt_num").value = "А" + dogNumFromDate(iso);
  const p = parseFloat($("price_num")?.value) || 0;
  const f = parseFloat($("fee_num")?.value) || 0;
  if ($("price_words_preview"))
    $("price_words_preview").textContent = "прописью: " + (p > 0 ? rublesToWords(p) : "—");
  if ($("fee_words_preview"))
    $("fee_words_preview").textContent = "прописью: " + (f > 0 ? rublesToWords(f) : "—");
  const vin = $("car_vin")?.value || "";
  const err = $("vin_err");
  if (err && $("car_vin")) {
    if (vin && !isValidVIN(vin)) {
      err.textContent = "VIN должен содержать 17 символов и не содержать I, O, Q";
      $("car_vin").classList.add("invalid");
    } else {
      err.textContent = "";
      $("car_vin").classList.remove("invalid");
    }
  }
}

function flashStatus(msg) {
  const s = $("status");
  if (!s) return;
  s.textContent = msg;
  setTimeout(() => {
    if (s.textContent === msg) s.textContent = "";
  }, 2500);
}

function prepareGeneration() {
  if (!$("komitent_fio").value.trim()) {
    alert("Заполните, как минимум, ФИО комитента и дату договора.");
    return null;
  }
  if (!$("dog_date").value) {
    alert("Укажите дату договора.");
    return null;
  }
  if ($("car_vin").value && !isValidVIN($("car_vin").value)) {
    if (!confirm("VIN не прошёл проверку. Продолжить генерацию?")) return null;
  }
  const ctx = buildContext();
  const surname = ctx.KOMITENT_FIO_SHORT.split(" ")[0] || "комитент";
  return { ctx, surname };
}

export function createCommissionDefaultData() {
  const t = new Date();
  const iso = `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`;
  return {
    docType: "commission",
    komitent_fio: "",
    komitent_sex: "m",
    komitent_phone: "",
    komitent_addr: "",
    komitent_passport: "",
    komitent_passport_issued: "",
    komitent_id: "",
    komitent_account: "",
    komitent_bank: "",
    komitent_bic: "",
    car_vin: "",
    car_make_model: "",
    car_year: "",
    car_plate: "",
    car_sts: "",
    car_engine: "",
    car_gearbox: "МКПП",
    car_drive: "Передний",
    car_color: "",
    car_type: "",
    car_keys: "2",
    car_mileage: "",
    dog_date: iso,
    dog_num: dogNumFromDate(iso),
    akt_num: "А" + dogNumFromDate(iso),
    price_num: "",
    fee_num: "",
    fuel_level: "",
    has_service_book: false,
    has_spare: true,
    has_jack: true,
    has_wrench: true,
    has_firstaid: true,
    has_ext: true,
    has_sign: true,
    lkp_measured: "не производился",
    diag_done: "не проводилась",
    defects: "",
    commission_member_1: "Герасимец М.С.",
  };
}

export async function mountCommission(container, { data, recordId, onChange, onSaved } = {}) {
  await Promise.all([ensureLibs(), ensureTemplates(), ensureFormHtml()]);
  if (!document.getElementById("commission-css")) {
    const link = document.createElement("link");
    link.id = "commission-css";
    link.rel = "stylesheet";
    link.href = "/static/contracts/commission/commission.css?v=20260910e";
    document.head.appendChild(link);
  }

  container.innerHTML = `<div class="commission-wrap">${formHtmlCache}</div>`;
  writeForm(data || createCommissionDefaultData());
  refreshPreviews();

  let currentId = recordId || null;
  let saveTimer = 0;
  const persist = async () => {
    const payload = readForm();
    onChange?.(payload);
    try {
      if (currentId) {
        await updateContract(currentId, payload);
        flashStatus("Сохранено");
        onSaved?.(currentId, payload);
      }
    } catch (err) {
      flashStatus(err.message || "Ошибка сохранения");
    }
  };
  const schedule = () => {
    onChange?.(readForm());
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(persist, 900);
  };

  container.addEventListener("input", (e) => {
    if (e.target.id === "car_vin") {
      e.target.value = e.target.value.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, "");
    }
    refreshPreviews();
    schedule();
  });
  container.addEventListener("change", () => {
    refreshPreviews();
    schedule();
  });

  $("gen_dogovor").onclick = async () => {
    const p = prepareGeneration();
    if (!p) return;
    try {
      await persist();
      const blob = buildDocxBlob(dogTpl, p.ctx);
      saveAs(blob, `Договор-комиссии_${p.ctx.DOG_NUM}_${p.surname}.docx`);
      flashStatus("Договор скачан");
    } catch (e) {
      console.error(e);
      alert("Ошибка: " + (e.message || e));
    }
  };
  $("gen_akt").onclick = async () => {
    const p = prepareGeneration();
    if (!p) return;
    try {
      await persist();
      const blob = buildDocxBlob(aktTpl, p.ctx);
      saveAs(blob, `Акт-приёма-передачи_${p.ctx.AKT_NUM}_${p.surname}.docx`);
      flashStatus("Акт скачан");
    } catch (e) {
      console.error(e);
      alert("Ошибка: " + (e.message || e));
    }
  };
  $("gen_both").onclick = async () => {
    const p = prepareGeneration();
    if (!p) return;
    try {
      await persist();
      const dogBlob = buildDocxBlob(dogTpl, p.ctx);
      const aktBlob = buildDocxBlob(aktTpl, p.ctx);
      const dogName = `Договор-комиссии_${p.ctx.DOG_NUM}_${p.surname}.docx`;
      const aktName = `Акт-приёма-передачи_${p.ctx.AKT_NUM}_${p.surname}.docx`;
      const zipOut = new PizZip();
      zipOut.file(dogName, new Uint8Array(await dogBlob.arrayBuffer()));
      zipOut.file(aktName, new Uint8Array(await aktBlob.arrayBuffer()));
      const zipBlob = new Blob([zipOut.generate({ type: "arraybuffer" })], {
        type: "application/zip",
      });
      saveAs(zipBlob, `Сделка_${p.ctx.DOG_NUM}_${p.surname}.zip`);
      flashStatus("Архив скачан");
    } catch (e) {
      console.error(e);
      alert("Ошибка: " + (e.message || e));
    }
  };
  $("save_local").textContent = "Сохранить";
  $("save_local").onclick = () => persist();
  $("load_example").onclick = () => {
    writeForm({
      ...createCommissionDefaultData(),
      komitent_fio: "Маркова Диана Олеговна",
      komitent_sex: "f",
      komitent_phone: "+375 29 000-00-00",
      komitent_addr: "г. Минск, ул. Маршала Лосика, д. 25, кв. 10",
      komitent_passport: "ВМ3183897",
      komitent_passport_issued: "03.03.2026 Оршанским РУВД Витебской области",
      komitent_id: "3220291Е026РВ7",
      car_vin: "WF0HXXWPBHAG47988",
      car_make_model: "FORD GRAND C-MAX",
      car_year: "2010",
      car_plate: "8АКТ0105",
      car_sts: "7TC0224207, выдано 14.04.2026",
      car_engine: "1.6 л, дизель",
      car_gearbox: "МКПП",
      car_drive: "Передний",
      car_color: "Серый",
      car_type: "Легковой автомобиль, минивэн",
      car_keys: "2",
      car_mileage: "270000",
      dog_date: "2026-05-06",
      price_num: "30000",
      fee_num: "900",
      fuel_level: "1/4 бака",
      defects:
        "Видимых дефектов кузова и салона, кроме нормального эксплуатационного износа, не выявлено.",
    });
    $("dog_num").value = "";
    $("akt_num").value = "";
    refreshPreviews();
    schedule();
    flashStatus("Пример загружен");
  };
  $("reset").onclick = () => {
    if (!confirm("Очистить все поля?")) return;
    writeForm(createCommissionDefaultData());
    refreshPreviews();
    schedule();
  };

  return {
    read: readForm,
    write: writeForm,
    setRecordId: (id) => {
      currentId = id;
    },
  };
}

export async function createCommissionRecord(initial = null) {
  const payload = { ...(initial || createCommissionDefaultData()), docType: "commission" };
  return createContract(payload);
}
