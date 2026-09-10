import { createDefaultData, SAMPLE_CLIENT } from "./lib/defaults.js";
import { buildContract } from "./lib/contract.js";
import { buildAct } from "./lib/act.js";
import { moneyPhrase } from "./lib/money.js";
import { suggestContractNumber, todayIso } from "./lib/format.js";
import { downloadWord, renderSheet } from "./render.js";
import { renderAnalysis, renderArchive, renderForm } from "./ui.js";
import {
  createContract,
  deleteContract,
  getContract,
  listContracts,
  updateContract,
} from "./lib/api.js";
import {
  createCommissionDefaultData,
  createCommissionRecord,
  mountCommission,
} from "./commission.js";

const titles = {
  archive: {
    h: "Архив договоров",
    p: "Подбор ЕС и комиссия. Откройте договор или создайте новый — всё сохраняется на сервере.",
  },
  contract: {
    h: "Договор подбора ЕС",
    p: "Заполните поля слева. Документ сам сохраняется; коллега увидит его в архиве.",
  },
  act: {
    h: "Акт сдачи-приёмки",
    p: "Акт закрывает услугу для учёта. Он привязан к этому же договору подбора.",
  },
  commission: {
    h: "Договор комиссии",
    p: "Бланк комиссии и акта приёма-передачи автомобиля. Скачайте Word после заполнения.",
  },
  analysis: {
    h: "Предложения по договору",
    p: "Юридические риски XL-шаблона и что изменено в генераторе подбора.",
  },
};

let view = "archive";
let tab = "archive";
let data = createDefaultData();
let recordId = null;
let records = [];
let query = "";
let formNeedsPaint = true;
let archiveError = "";
let saveState = "";
let saveTimer = 0;
let commissionMount = null;

function isCommission(payload = data) {
  return payload?.docType === "commission";
}

function setSaveStatus(text) {
  saveState = text;
  const el = document.getElementById("save-status");
  if (el) el.textContent = text;
}

async function persist() {
  if (!recordId || isCommission()) return;
  try {
    setSaveStatus("Сохранение…");
    await updateContract(recordId, data);
    setSaveStatus("Сохранено");
  } catch (err) {
    setSaveStatus(err.message || "Не удалось сохранить");
  }
}

function scheduleSave() {
  window.clearTimeout(saveTimer);
  setSaveStatus("Есть несохранённые правки");
  saveTimer = window.setTimeout(() => persist(), 900);
}

function amountLabel() {
  if (isCommission()) {
    const fee = parseFloat(data.fee_num) || 0;
    return fee ? moneyPhrase(fee) : moneyPhrase(data.price_num || 0);
  }
  return moneyPhrase(data.amount);
}

async function paint() {
  const workspace = document.getElementById("workspace");
  const single = document.getElementById("single-pane");
  const formPane = document.getElementById("form-pane");
  const preview = document.getElementById("preview-pane");

  document.getElementById("amount-box").textContent = amountLabel();
  document.getElementById("save-status").textContent =
    view === "editor" || tab === "commission" ? saveState : "";

  const screen = tab === "archive" ? "archive" : tab;
  document.getElementById("toolbar-title").textContent = titles[screen]?.h || "";
  document.getElementById("toolbar-lead").textContent = titles[screen]?.p || "";
  const selectionEditor = tab === "contract" || tab === "act";
  document.getElementById("doc-actions").hidden = !selectionEditor || isCommission();
  document.getElementById("btn-sample").hidden = tab !== "contract" || isCommission();

  document.querySelectorAll(".rail nav button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  if (tab === "archive") {
    commissionMount = null;
    const activeSearch = document.activeElement?.dataset?.action === "search";
    const caret = activeSearch ? document.activeElement.selectionStart : null;
    workspace.hidden = true;
    single.hidden = false;
    single.innerHTML = renderArchive({ rows: records, query, error: archiveError });
    const search = single.querySelector("[data-action=search]");
    if (activeSearch && search) {
      search.focus();
      if (caret != null) search.setSelectionRange(caret, caret);
    }
    return;
  }

  if (tab === "analysis") {
    commissionMount = null;
    workspace.hidden = true;
    single.hidden = false;
    single.innerHTML = renderAnalysis();
    return;
  }

  if (tab === "commission") {
    workspace.hidden = true;
    single.hidden = false;
    view = "editor";
    setSaveStatus(recordId ? "Сохранено" : "");
    commissionMount = await mountCommission(single, {
      data,
      recordId,
      onChange: (payload) => {
        data = payload;
        document.getElementById("amount-box").textContent = amountLabel();
        setSaveStatus("Есть несохранённые правки");
      },
      onSaved: (id) => {
        recordId = id;
        setSaveStatus("Сохранено");
      },
    });
    return;
  }

  commissionMount = null;
  view = "editor";
  workspace.hidden = false;
  single.hidden = true;
  formPane.hidden = false;
  preview.hidden = false;
  if (formNeedsPaint) {
    formPane.innerHTML = renderForm(data);
    formNeedsPaint = false;
  }
  preview.innerHTML = renderSheet(tab === "act" ? buildAct(data) : buildContract(data));
}

async function loadArchive() {
  archiveError = "";
  try {
    records = await listContracts();
  } catch (err) {
    records = [];
    archiveError = err.message;
  }
}

async function openRecord(id) {
  const row = await getContract(id);
  if (!row) throw new Error("Договор не найден.");
  recordId = row.id;
  const payload = row.payload || {};
  if (payload.docType === "commission") {
    data = { ...createCommissionDefaultData(), ...payload, docType: "commission" };
    tab = "commission";
  } else {
    data = { ...createDefaultData(), ...payload, docType: "selection" };
    formNeedsPaint = true;
    tab = "contract";
  }
  view = "editor";
  setSaveStatus("Сохранено");
  await paint();
}

async function createNewSelection() {
  data = createDefaultData();
  formNeedsPaint = true;
  const row = await createContract(data);
  recordId = row.id;
  view = "editor";
  tab = "contract";
  setSaveStatus("Сохранено");
  await paint();
}

async function createNewCommission() {
  data = createCommissionDefaultData();
  const row = await createCommissionRecord(data);
  recordId = row.id;
  data = { ...data, ...(row.payload || {}) };
  view = "editor";
  tab = "commission";
  setSaveStatus("Сохранено");
  await paint();
}

document.getElementById("form-pane").addEventListener("input", (e) => {
  if (isCommission()) return;
  const name = e.target.name;
  if (!name) return;
  const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
  data = { ...data, [name]: value };
  if (name === "clientType") formNeedsPaint = true;
  scheduleSave();
  paint();
});

document.getElementById("form-pane").addEventListener("change", (e) => {
  if (isCommission()) return;
  const name = e.target.name;
  if (!name) return;
  const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
  data = { ...data, [name]: value };
  if (name === "clientType") formNeedsPaint = true;
  scheduleSave();
  paint();
});

document.querySelectorAll(".rail nav button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    tab = btn.dataset.tab;
    try {
      if (tab === "archive") {
        view = "archive";
        await loadArchive();
      } else if (tab === "analysis") {
        view = "editor";
      } else if (tab === "commission") {
        if (!recordId || !isCommission()) await createNewCommission();
        else view = "editor";
      } else {
        if (!recordId || isCommission()) await createNewSelection();
        else {
          view = "editor";
          formNeedsPaint = true;
        }
      }
      await paint();
    } catch (err) {
      archiveError = err.message;
      await paint();
    }
  });
});

document.body.addEventListener("input", (e) => {
  if (e.target.dataset.action === "search") {
    query = e.target.value;
    paint();
  }
});

document.body.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  try {
    if (action === "new") {
      await createNewSelection();
    } else if (action === "new-commission") {
      await createNewCommission();
    } else if (action === "open") {
      await openRecord(btn.dataset.id);
    } else if (action === "delete") {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm("Удалить договор? Это увидят и другие администраторы.")) return;
      await deleteContract(btn.dataset.id);
      if (String(recordId) === String(btn.dataset.id)) recordId = null;
      await loadArchive();
      tab = "archive";
      view = "archive";
      await paint();
    } else if (action === "sample") {
      if (isCommission()) return;
      const date = data.contractDate || todayIso();
      data = {
        ...data,
        ...SAMPLE_CLIENT,
        contractNumber: data.contractNumber || suggestContractNumber(date),
        contractDate: date,
        actDate: data.actDate || date,
        serviceFrom: date,
        serviceTo: data.actDate || date,
      };
      formNeedsPaint = true;
      tab = "contract";
      scheduleSave();
      await paint();
    } else if (action === "print") {
      window.print();
    } else if (action === "word") {
      const stamp = data.contractNumber || "draft";
      downloadWord(
        tab === "act" ? buildAct(data) : buildContract(data),
        `${tab === "act" ? "Akt" : "Dogovor"}_${stamp}.doc`,
      );
    } else if (action === "both") {
      const stamp = data.contractNumber || "draft";
      downloadWord(buildContract(data), `Dogovor_${stamp}.doc`);
      setTimeout(() => downloadWord(buildAct(data), `Akt_${stamp}.doc`), 400);
    }
  } catch (err) {
    archiveError = err.message;
    await paint();
  }
});

async function boot() {
  try {
    await loadArchive();
    view = "archive";
    tab = "archive";
  } catch (err) {
    archiveError = err.message;
  }
  await paint();
}

boot();
