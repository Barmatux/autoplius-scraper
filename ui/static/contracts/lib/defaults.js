import { suggestContractNumber, todayIso } from "./format.js";

function executorFromPage() {
  const raw = typeof window !== "undefined" ? window.__CONTRACT_DEFAULTS__ : null;
  return raw && typeof raw === "object" ? raw : {};
}

export function createDefaultData() {
  const date = todayIso();
  const ex = executorFromPage();
  return {
    contractNumber: suggestContractNumber(date),
    contractDate: date,
    city: "Минск",

    clientType: "individual",
    gender: "male",
    clientName: "",
    clientAddress: "",
    passport: "",
    passportIssuer: "",
    passportDate: "",
    personalNumber: "",
    clientPhone: "",
    clientEmail: "",
    clientMessenger: "Viber / Telegram / WhatsApp",

    clientCompany: "",
    clientUnp: "",
    clientDirector: "",
    clientDirectorGenitive: "",
    clientBasis: "Устава",
    clientBankDetails: "",

    amount: "1000",
    vatMode: "none",
    prepaidDays: "20",
    invoicePayDays: "2",
    bidReplyTime: "17:00",
    refundDays: "15",
    actReviewDays: "5",
    penaltyPercent: "10",

    vehicleMake: "",
    vehicleModel: "",
    vehicleYearFrom: "",
    vehicleYearTo: "",
    vehicleBudget: "",
    vehicleBudgetCurrency: "EUR",
    marketplace: "аукционы и дилерские площадки ЕС",
    vehicleNotes: "",

    actNumber: "",
    actDate: date,
    serviceFrom: date,
    serviceTo: date,
    serviceDescription:
      "Информационно-консультационные услуги по подбору транспортного средства на рынке Европейского союза и информационному сопровождению его приобретения",

    photoConsent: false,

    executorName: ex.executorName || "EuroHUB",
    executorShort: ex.executorShort || "EuroHUB",
    executorUnp: ex.executorUnp || "",
    executorAddress: ex.executorAddress || "",
    executorEmail: ex.executorEmail || "",
    executorPhone: ex.executorPhone || "",
    executorDirector: ex.executorDirector || "",
    executorDirectorShort: ex.executorDirectorShort || "",
    executorDirectorGenitive: ex.executorDirectorGenitive || "",
    executorAccount: ex.executorAccount || "",
    executorBank: ex.executorBank || "",
    executorSwift: ex.executorSwift || "",
    executorBankUnp: ex.executorBankUnp || "",
    executorOkpo: ex.executorOkpo || "",
  };
}

export const SAMPLE_CLIENT = {
  clientType: "individual",
  gender: "male",
  clientName: "Каржицкий Александр Сергеевич",
  clientAddress: "Витебская обл., г. Орша, ул. Владимира Ленина, д. 63, кв. 55",
  passport: "BM1964183",
  passportIssuer: "Октябрьским РОВД г. Орши",
  passportDate: "2012-01-26",
  personalNumber: "3241286E025PB7",
  clientPhone: "+375 (33) 647-47-10",
  clientEmail: "",
  clientMessenger: "Viber",
  amount: "1000",
  vehicleMake: "",
  vehicleModel: "",
  vehicleBudget: "",
  marketplace: "аукционы и дилерские площадки ЕС",
};
