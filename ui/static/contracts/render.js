export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function blockHtml(block) {
  if (block.type === "heading") return `<h2 class="sheet-h">${escapeHtml(block.text)}</h2>`;
  if (block.type === "title") return `<h2 class="sheet-h center">${escapeHtml(block.text)}</h2>`;
  if (block.type === "p") return `<p class="sheet-p">${escapeHtml(block.text)}</p>`;
  if (block.type === "note") return `<p class="sheet-note">${escapeHtml(block.text)}</p>`;
  if (block.type === "space") return `<p class="sheet-space">&nbsp;</p>`;
  if (block.type === "kv") {
    const rows = block.rows
      .map(
        ([k, v]) =>
          `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`,
      )
      .join("");
    return `<table class="sheet-kv" width="100%" cellspacing="0" cellpadding="4"><tbody>${rows}</tbody></table>`;
  }
  if (block.type === "table") {
    const head = block.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
    const body = block.rows
      .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
      .join("");
    return `<table class="sheet-table" width="100%" cellspacing="0" cellpadding="4"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  return "";
}

function metaHtml(meta) {
  return `<table class="sheet-meta" width="100%" cellspacing="0" cellpadding="0">
    <tr>
      <td class="meta-city" align="left" width="50%">${escapeHtml(meta.city)}</td>
      <td class="meta-date" align="right" width="50%">${escapeHtml(meta.date)}</td>
    </tr>
  </table>`;
}

function signsHtml(sig, { showLeftStamp = true, showRightStamp = true } = {}) {
  const lines = (items) =>
    (items || [])
      .filter((line) => line != null && String(line).trim() !== "")
      .map((line) => `<p class="sign-line-text">${escapeHtml(line)}</p>`)
      .join("");

  const col = (title, items, role, sign, showStamp) => `
    <td class="sign-col" width="48%" valign="top">
      <p class="sign-title">${escapeHtml(title)}</p>
      ${lines(items)}
      <p class="sign-gap">&nbsp;</p>
      <p class="sign-role">${escapeHtml(role)}</p>
      <p class="sign-line">${escapeHtml(sign)}</p>
      ${showStamp ? `<p class="sign-stamp">М.П. (при использовании печати)</p>` : `<p class="sign-stamp">&nbsp;</p>`}
    </td>`;

  return `<table class="signs" width="100%" cellspacing="0" cellpadding="0">
    <tr>
      ${col(sig.leftTitle, sig.leftLines, sig.leftRole, sig.leftSign, showLeftStamp)}
      <td width="4%">&nbsp;</td>
      ${col(sig.rightTitle, sig.rightLines, sig.rightRole, sig.rightSign, showRightStamp)}
    </tr>
  </table>`;
}

function stampOptions(doc) {
  const individual = doc.clientType === "individual";
  return {
    showLeftStamp: true,
    showRightStamp: !individual,
  };
}

function headerHtml(doc) {
  return `
    <div class="sheet-kicker">${escapeHtml(doc.kicker)}</div>
    <h1 class="sheet-title">${escapeHtml(doc.title)}</h1>
    ${(doc.subtitle || []).map((line) => `<p class="sheet-sub">${escapeHtml(line)}</p>`).join("")}
    ${metaHtml(doc.meta)}
    ${doc.preamble ? `<p class="sheet-p preamble">${escapeHtml(doc.preamble)}</p>` : ""}`;
}

function splitRequisitesBlocks(blocks = []) {
  const idx = blocks.findIndex(
    (b) => b.type === "heading" && /РЕКВИЗИТЫ/i.test(String(b.text || "")),
  );
  if (idx < 0) return { body: blocks, requisites: [] };
  let bodyEnd = idx;
  while (bodyEnd > 0 && blocks[bodyEnd - 1].type === "space") bodyEnd -= 1;
  return { body: blocks.slice(0, bodyEnd), requisites: blocks.slice(idx) };
}

/** Screen / print preview */
export function renderSheet(doc) {
  const stamps = stampOptions(doc);
  const annex = doc.annex1
    ? `<div class="sheet-annex">${doc.annex1.map(blockHtml).join("")}${signsHtml(doc.signatures, stamps)}</div>`
    : "";
  return `
    <article class="sheet">
      ${headerHtml(doc)}
      ${(doc.blocks || []).map(blockHtml).join("")}
      ${signsHtml(doc.signatures, stamps)}
      ${annex}
    </article>`;
}

function wordStyles() {
  return `
  @page Section1 {
    size: 210mm 297mm;
    margin: 12mm 12mm 22mm 12mm;
    mso-header-margin: 6mm;
    mso-footer-margin: 8mm;
    mso-footer: f1;
  }
  @page Section2 {
    size: 210mm 297mm;
    margin: 12mm 12mm 14mm 12mm;
    mso-header-margin: 6mm;
    mso-footer-margin: 8mm;
    mso-footer: f2;
  }
  div.Section1 { page: Section1; }
  div.Section2 { page: Section2; }
  body { font-family: "Times New Roman", Times, serif; font-size: 11pt; color: #1c1916; margin: 0; }
  .sheet-kicker { text-align: center; font-size: 9pt; letter-spacing: .1em; text-transform: uppercase; margin: 0 0 4pt; }
  .sheet-title { text-align: center; font-size: 15pt; margin: 4pt 0 2pt; font-weight: bold; }
  .sheet-sub { text-align: center; font-style: italic; margin: 0; font-size: 11pt; }
  .sheet-meta { width: 100%; border-collapse: collapse; margin: 8pt 0 6pt; }
  .sheet-meta td { border: 0; padding: 0; font-size: 11pt; vertical-align: top; }
  .meta-city { text-align: left; }
  .meta-date { text-align: right; }
  .sheet-h { font-size: 11pt; margin: 8pt 0 3pt; font-weight: bold; }
  .sheet-h.center { text-align: center; }
  .sheet-p { text-align: justify; margin: 0 0 4pt; line-height: 1.25; }
  .sheet-p.preamble { text-indent: 1.1em; }
  .sheet-note { font-size: 9pt; font-style: italic; color: #555; margin: 4pt 0 0; }
  .sheet-space { margin: 2pt 0; font-size: 6pt; line-height: 6pt; }
  table.sheet-kv, table.sheet-table { border-collapse: collapse; width: 100%; margin: 4pt 0 6pt; font-size: 10pt; }
  table.sheet-kv th, table.sheet-kv td,
  table.sheet-table th, table.sheet-table td { border: 1px solid #c4b49a; padding: 2pt 4pt; vertical-align: top; }
  table.sheet-kv th, table.sheet-table th { background: #efe8dc; text-align: left; font-weight: bold; }
  table.sheet-kv th { width: 34%; }
  table.signs { width: 100%; border-collapse: collapse; margin-top: 10pt; font-size: 10pt; }
  table.signs td { border: 0; padding: 0; vertical-align: top; }
  .sign-title { font-weight: bold; margin: 0 0 4pt; }
  .sign-line-text { margin: 0 0 1pt; }
  .sign-gap { margin: 6pt 0; font-size: 8pt; line-height: 8pt; }
  .sign-role { font-style: italic; color: #555; margin: 0; font-size: 9pt; }
  .sign-line { margin: 2pt 0 0; }
  .sign-stamp { margin: 2pt 0 0; color: #555; font-size: 9pt; }
  .sheet-annex { margin-top: 0; padding-top: 0; }
  p.MsoFooter { margin: 0; font-family: "Times New Roman", Times, serif; font-size: 9pt; }
`;
}

function footerSignNames(doc) {
  const fromLine = (sign) => {
    const m = String(sign || "").match(/\/\s*([^/]+?)\s*\//);
    const name = (m && m[1].trim()) || "";
    return name && !/^_+$/.test(name) ? name : "";
  };
  return {
    executor: fromLine(doc.signatures?.leftSign) || "__________",
    client: fromLine(doc.signatures?.rightSign) || "__________",
  };
}

function wordFooterWithSignatures(doc) {
  const { executor, client } = footerSignNames(doc);
  return `<div style='mso-element:footer' id=f1>
  <p class="MsoFooter">
    Исполнитель ________________ / ${escapeHtml(executor)} /&nbsp;&nbsp;&nbsp;&nbsp;Заказчик ________________ / ${escapeHtml(client)} /
    <span style="mso-tab-count:1"> </span>
    стр.&nbsp;<span style='mso-field-code:" PAGE "'></span>
  </p>
</div>`;
}

function wordFooterPageOnly() {
  return `<div style='mso-element:footer' id=f2>
  <p class="MsoFooter" align="center">стр.&nbsp;<span style='mso-field-code:" PAGE "'></span></p>
</div>`;
}

function wordBodyHtml(doc) {
  const stamps = stampOptions(doc);
  if (doc.kind === "contract" && doc.annex1) {
    const { body, requisites } = splitRequisitesBlocks(doc.blocks || []);
    return `
<div class="Section1">
  ${headerHtml(doc)}
  ${body.map(blockHtml).join("")}
</div>
<br clear="all" style="page-break-before:always; mso-break-type:section-break" />
<div class="Section2">
  ${requisites.map(blockHtml).join("")}
  ${signsHtml(doc.signatures, stamps)}
  <br clear="all" style="page-break-before:always" />
  <div class="sheet-annex">
    ${doc.annex1.map(blockHtml).join("")}
    ${signsHtml(doc.signatures, stamps)}
  </div>
</div>
${wordFooterWithSignatures(doc)}
${wordFooterPageOnly()}`;
  }

  return `
<div class="Section1">
  ${headerHtml(doc)}
  ${(doc.blocks || []).map(blockHtml).join("")}
  ${signsHtml(doc.signatures, stamps)}
</div>
${wordFooterWithSignatures(doc)}
${wordFooterPageOnly()}`;
}

export function downloadWord(doc, filename) {
  const html = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:w="urn:schemas-microsoft-com:office:word"
 xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8" />
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>${escapeHtml(doc.title)}</title>
<!--[if gte mso 9]>
<xml>
  <w:WordDocument>
    <w:View>Print</w:View>
    <w:Zoom>100</w:Zoom>
    <w:DoNotOptimizeForBrowser/>
  </w:WordDocument>
</xml>
<![endif]-->
<style>
${wordStyles()}
</style>
</head>
<body>
${wordBodyHtml(doc)}
</body>
</html>`;
  const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith(".doc") ? filename : `${filename}.doc`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
