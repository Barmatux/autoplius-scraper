(function () {
  function setStatus(row, message, kind) {
    var status = row.querySelector("[data-catalog-status]");
    if (!status) return;
    status.textContent = message || "";
    status.className = "catalog-save-status" + (kind ? " is-" + kind : "");
  }

  function adjustPill(labelPrefix, delta) {
    if (!delta) return;
    var pill = Array.prototype.find.call(document.querySelectorAll(".meta .pill"), function (node) {
      return (node.textContent || "").trim().indexOf(labelPrefix) === 0;
    });
    if (!pill) return;
    var match = pill.textContent.match(/(\d+)\s*$/);
    if (!match) return;
    var next = Math.max(0, parseInt(match[1], 10) + delta);
    pill.textContent = labelPrefix + next;
  }

  function cleanupEmptyCatalogBlocks(root) {
    if (!root) return;
    root.querySelectorAll(".catalog-model-block").forEach(function (modelBlock) {
      if (!modelBlock.querySelector("[data-catalog-row]")) {
        modelBlock.remove();
      }
    });
    root.querySelectorAll(".catalog-make-block").forEach(function (makeBlock) {
      if (!makeBlock.querySelector("[data-catalog-row]")) {
        makeBlock.remove();
      }
    });
    var newSection = document.querySelector(".catalog-new-section");
    if (newSection && !newSection.querySelector("[data-catalog-row]")) {
      newSection.remove();
    }
  }

  function ensureMainSection() {
    var tree = document.querySelector(".catalog-tree");
    if (!tree) return null;
    var mainSection = tree.querySelector(".catalog-main-section");
    if (mainSection) return mainSection;

    mainSection = document.createElement("section");
    mainSection.className = "catalog-main-section";
    var head = document.createElement("div");
    head.className = "catalog-section-head";
    head.innerHTML = '<h2 class="catalog-section-title">Основной каталог</h2>';
    mainSection.appendChild(head);
    tree.appendChild(mainSection);
    return mainSection;
  }

  function findMakeBlock(section, make) {
    return Array.prototype.find.call(section.querySelectorAll(".catalog-make-block"), function (block) {
      return block.querySelector(".catalog-make-title")?.textContent.trim() === make;
    }) || null;
  }

  function findModelBlock(makeBlock, model) {
    var modelLabel = model || "—";
    return Array.prototype.find.call(makeBlock.querySelectorAll(".catalog-model-block"), function (block) {
      return block.querySelector(".catalog-model-title")?.textContent.trim() === modelLabel;
    }) || null;
  }

  function cloneMakeBlock(sourceMake, make) {
    var makeBlock = sourceMake.cloneNode(true);
    makeBlock.classList.remove("catalog-new-block");
    makeBlock.querySelectorAll("[data-catalog-row]").forEach(function (row) {
      row.remove();
    });
    makeBlock.querySelectorAll(".catalog-model-block").forEach(function (modelBlock) {
      modelBlock.remove();
    });
    var title = makeBlock.querySelector(".catalog-make-title");
    if (title) title.textContent = make;
    return makeBlock;
  }

  function cloneModelBlock(sourceModel, model) {
    var modelBlock = sourceModel.cloneNode(true);
    modelBlock.querySelectorAll("[data-catalog-row]").forEach(function (row) {
      row.remove();
    });
    var title = modelBlock.querySelector(".catalog-model-title");
    if (title) title.textContent = model || "—";
    return modelBlock;
  }

  function findOrCreateMainTbody(mainSection, make, model, row) {
    var sourceMake = row.closest(".catalog-make-block");
    var sourceModel = row.closest(".catalog-model-block");
    if (!sourceMake || !sourceModel) return null;

    var makeBlock = findMakeBlock(mainSection, make);
    if (!makeBlock) {
      makeBlock = cloneMakeBlock(sourceMake, make);
      mainSection.appendChild(makeBlock);
    }

    var modelBlock = findModelBlock(makeBlock, model);
    if (!modelBlock) {
      modelBlock = cloneModelBlock(sourceModel, model);
      makeBlock.appendChild(modelBlock);
    }

    return modelBlock.querySelector("tbody");
  }

  function promoteNewRow(row, wasMissing) {
    var make = row.getAttribute("data-make") || "";
    var model = row.getAttribute("data-model") || "";
    var mainSection = ensureMainSection();
    if (!mainSection) return;

    var tbody = findOrCreateMainTbody(mainSection, make, model, row);
    if (!tbody) return;

    row.removeAttribute("data-catalog-new");
    row.classList.remove("catalog-row-new");
    tbody.appendChild(row);

    cleanupEmptyCatalogBlocks(document.querySelector(".catalog-new-section"));
    adjustPill("Новые:", -1);
    if (wasMissing) {
      adjustPill("Заполнено:", 1);
      adjustPill("Без объёма:", -1);
    }
    adjustPill("Вручную:", 1);
  }

  async function saveRow(row) {
    var entryId = row.getAttribute("data-entry-id");
    var input = row.querySelector(".catalog-cm3-input");
    if (!entryId || !input) return;

    var wasMissing = row.classList.contains("catalog-row-missing");
    var wasNew = row.getAttribute("data-catalog-new") === "1";
    var raw = input.value.trim();
    var payload = { customs_cm3: raw === "" ? null : Number(raw) };
    if (raw !== "" && (!Number.isFinite(payload.customs_cm3) || payload.customs_cm3 <= 0)) {
      setStatus(row, "Некорректный объём", "error");
      return;
    }

    setStatus(row, "Сохранение…", "pending");
    try {
      var response = await fetch("/api/catalog/" + entryId, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      });
      var data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error((data && data.error) || "save failed");
      }
      row.classList.toggle("catalog-row-missing", payload.customs_cm3 === null);
      row.classList.toggle("catalog-row-manual", payload.customs_cm3 !== null);
      setStatus(row, "Сохранено", "ok");

      if (wasNew && payload.customs_cm3 !== null) {
        promoteNewRow(row, wasMissing);
      }

      window.setTimeout(function () {
        setStatus(row, "", "");
      }, 1800);
    } catch (_err) {
      setStatus(row, "Ошибка", "error");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-catalog-save]").forEach(function (button) {
      button.addEventListener("click", function () {
        var row = button.closest("[data-catalog-row]");
        if (row) saveRow(row);
      });
    });

    document.querySelectorAll(".catalog-cm3-input").forEach(function (input) {
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          var row = input.closest("[data-catalog-row]");
          if (row) saveRow(row);
        }
      });
    });
  });
})();
