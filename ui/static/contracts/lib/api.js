const API = "/admin/api/contracts";

async function apiFetch(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await res.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = raw;
  }
  if (!res.ok) {
    const msg = data?.error || data?.message || raw || "Ошибка запроса";
    throw new Error(String(msg));
  }
  return data;
}

function metaFromPayload(payload) {
  if (payload?.docType === "commission") {
    return {
      contract_number: payload.dog_num || "",
      client_name: payload.komitent_fio || "",
      amount: String(payload.fee_num || payload.price_num || ""),
      payload,
    };
  }
  const clientName =
    payload.clientType === "legal" ? payload.clientCompany || "" : payload.clientName || "";
  return {
    contract_number: payload.contractNumber || "",
    client_name: clientName,
    amount: String(payload.amount || ""),
    payload,
  };
}

export async function listContracts() {
  return apiFetch(API);
}

export async function getContract(id) {
  return apiFetch(`${API}/${encodeURIComponent(id)}`);
}

export async function createContract(payload) {
  return apiFetch(API, { method: "POST", body: metaFromPayload(payload) });
}

export async function updateContract(id, payload) {
  return apiFetch(`${API}/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: metaFromPayload(payload),
  });
}

export async function deleteContract(id) {
  await apiFetch(`${API}/${encodeURIComponent(id)}`, { method: "DELETE" });
}
