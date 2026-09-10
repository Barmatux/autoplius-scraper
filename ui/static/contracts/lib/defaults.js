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

    executorName: ex.executorName || "Общество с ограниченной ответственностью «Сканди Моторс»",
    executorShort: ex.executorShort || "ООО «Сканди Моторс»",
    executorUnp: ex.executorUnp || "193866357",
    executorAddress: ex.executorAddress || "г. Минск, ул. Скрыганова, дом 6, помещение 7",
    executorEmail: ex.executorEmail || "scandimotorsby@gmail.com",
    executorPhone: ex.executorPhone || "+375 (33) 698-77-99",
    executorDirector: ex.executorDirector || "Герасимец Максим Сергеевич",
    executorDirectorShort: ex.executorDirectorShort || "Герасимец М.С.",
    executorDirectorGenitive: ex.executorDirectorGenitive || "Герасимца Максима Сергеевича",
    executorAccount: ex.executorAccount || "BY58 ALFA 3012 2G91 3900 1027 0000",
    executorBank: ex.executorBank || "ЗАО «Альфа-Банк», 220013, г. Минск, ул. Сурганова, 43-47",
    executorSwift: ex.executorSwift || "ALFABY2X",
    executorBankUnp: ex.executorBankUnp || "101541947",
    executorOkpo: ex.executorOkpo || "37526626",
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
