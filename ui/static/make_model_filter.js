(function () {
  function initMakeModelFilter(root) {
    if (!root || root.dataset.mmInit === "1") return;
    root.dataset.mmInit = "1";

    var config = {};
    try {
      config = JSON.parse(root.getAttribute("data-make-model-config") || "{}");
    } catch (_err) {
      config = {};
    }

    var rowsContainer = root.querySelector(".vehicle-hierarchy-rows");
    var addButton = root.querySelector(".vehicle-hierarchy-add");
    if (!rowsContainer) return;

    var labels = { make: "Марка", model: "Модель" };
    var modelMap = config.modelMap || {};
    var makes = (config.makes || []).slice().sort(function (a, b) {
      return a.localeCompare(b, "ru");
    });

    function rowValues(row) {
      return {
        make: row.querySelector('[data-tier="make"]')?.value || "",
        model: row.querySelector('[data-tier="model"]')?.value || "",
      };
    }

    function fillSelect(select, options, placeholder, selected) {
      select.innerHTML = "";
      var empty = document.createElement("option");
      empty.value = "";
      empty.textContent = placeholder;
      select.appendChild(empty);
      options.forEach(function (value) {
        var option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        if (value === selected) option.selected = true;
        select.appendChild(option);
      });
    }

    function syncRowSelects(row, values) {
      var makeSelect = row.querySelector('[data-tier="make"]');
      var modelSelect = row.querySelector('[data-tier="model"]');
      if (!makeSelect || !modelSelect) return;

      fillSelect(makeSelect, makes, labels.make, values.make);

      var models = values.make ? (modelMap[values.make] || []).slice() : [];
      fillSelect(modelSelect, models, labels.model, values.model);
      modelSelect.disabled = !values.make;
    }

    function createRow(values) {
      values = values || { make: "", model: "" };
      var row = document.createElement("div");
      row.className = "vehicle-hierarchy-row";
      row.innerHTML =
        '<label class="vehicle-hierarchy-field">' +
        '<span class="vehicle-hierarchy-label">' +
        labels.make +
        "</span>" +
        '<select name="make" data-tier="make"></select>' +
        "</label>" +
        '<label class="vehicle-hierarchy-field">' +
        '<span class="vehicle-hierarchy-label">' +
        labels.model +
        "</span>" +
        '<select name="model" data-tier="model"></select>' +
        "</label>" +
        '<button type="button" class="vehicle-hierarchy-remove" aria-label="Удалить строку">×</button>';

      syncRowSelects(row, values);
      bindRow(row);
      return row;
    }

    function bindRow(row) {
      var makeSelect = row.querySelector('[data-tier="make"]');
      var modelSelect = row.querySelector('[data-tier="model"]');
      var removeButton = row.querySelector(".vehicle-hierarchy-remove");

      makeSelect.addEventListener("change", function () {
        syncRowSelects(row, { make: makeSelect.value, model: "" });
      });

      removeButton.addEventListener("click", function () {
        var rows = rowsContainer.querySelectorAll(".vehicle-hierarchy-row");
        if (rows.length <= 1) {
          syncRowSelects(row, { make: "", model: "" });
          return;
        }
        row.remove();
      });
    }

    rowsContainer.querySelectorAll(".vehicle-hierarchy-row").forEach(function (row) {
      bindRow(row);
      syncRowSelects(row, rowValues(row));
    });

    if (addButton) {
      addButton.addEventListener("click", function () {
        rowsContainer.appendChild(createRow());
      });
    }

    var form = root.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        rowsContainer.querySelectorAll(".vehicle-hierarchy-row").forEach(function (row) {
          var values = rowValues(row);
          if (!values.make && !values.model) {
            row.remove();
          }
        });
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-make-model-filter]").forEach(initMakeModelFilter);
  });
})();
