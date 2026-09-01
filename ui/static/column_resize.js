(function () {
  const LOCAL_KEY = "listings-table-col-widths-v2";
  const MIN_WIDTH = 56;
  const API_URL = "/api/table-layout";

  document.querySelectorAll("[data-col-resize]").forEach(initTable);

  function initTable(table) {
    const editable = table.hasAttribute("data-col-resize-editable");
    const cols = [...table.querySelectorAll("colgroup col[data-col]")];
    const headers = [...table.querySelectorAll("thead th")];
    if (!cols.length || cols.length !== headers.length) {
      return;
    }

    const controls = document.querySelector("[data-table-layout-controls]");
    const saveBtn = controls?.querySelector("[data-table-layout-save]");
    const resetBtn = controls?.querySelector("[data-table-layout-reset]");
    const statusEl = controls?.querySelector("[data-table-layout-status]");

    void bootstrapLayout(table, cols, headers, editable).then(() => {
      if (!editable) {
        return;
      }
      headers.forEach((th, index) => {
        if (index >= headers.length - 1) {
          return;
        }
        const handle = document.createElement("span");
        handle.className = "col-resize-handle";
        handle.setAttribute("role", "separator");
        handle.setAttribute("aria-orientation", "vertical");
        handle.setAttribute("aria-label", "Изменить ширину столбца");
        handle.title = "Потяните, чтобы изменить ширину";
        th.appendChild(handle);
        handle.addEventListener("mousedown", (event) => {
          event.preventDefault();
          event.stopPropagation();
          startResize(event, cols, headers, index, statusEl);
        });
      });
    });

    saveBtn?.addEventListener("click", () => {
      void saveToServer(cols, statusEl, saveBtn);
    });

    resetBtn?.addEventListener("click", () => {
      try {
        localStorage.removeItem(LOCAL_KEY);
      } catch (_err) {
        /* ignore */
      }
      cols.forEach((col) => {
        col.style.width = "";
      });
      setStatus(statusEl, "Разметка сброшена. Обновите страницу.", "info");
    });
  }

  async function bootstrapLayout(table, cols, headers, editable) {
    table.offsetWidth;
    let widths = readEmbeddedLayout(table);
    if (!widths && editable) {
      widths = loadLocal();
    }
    if (!widths && editable) {
      try {
        const response = await fetch(API_URL, { headers: { Accept: "application/json" } });
        if (response.ok) {
          const payload = await response.json();
          if (payload?.widths && typeof payload.widths === "object") {
            widths = payload.widths;
          }
        }
      } catch (_err) {
        /* offline or API unavailable */
      }
    }
    if (widths) {
      applyWidths(cols, widths);
      return;
    }
    if (editable) {
      snapshotWidths(cols, headers);
    }
  }

  function readEmbeddedLayout(table) {
    const raw = table.dataset.savedLayout;
    if (!raw) {
      return null;
    }
    try {
      const payload = JSON.parse(raw);
      return payload?.widths && typeof payload.widths === "object" ? payload.widths : null;
    } catch (_err) {
      return null;
    }
  }

  function readColWidth(col, header) {
    const inline = parseFloat(col.style.width);
    if (!Number.isNaN(inline) && inline > 0) {
      return inline;
    }
    return header.getBoundingClientRect().width;
  }

  function snapshotWidths(cols, headers) {
    cols.forEach((col, index) => {
      col.style.width = `${headers[index].getBoundingClientRect().width}px`;
    });
    saveLocal(cols);
  }

  function startResize(event, cols, headers, index, statusEl) {
    const leftCol = cols[index];
    const rightCol = cols[index + 1];
    const startX = event.clientX;
    const startLeft = readColWidth(leftCol, headers[index]);
    const startRight = readColWidth(rightCol, headers[index + 1]);

    document.body.classList.add("col-resize-active");
    setStatus(statusEl, "Тянете границу столбца…", "info");

    function onMove(moveEvent) {
      const delta = moveEvent.clientX - startX;
      let newLeft = startLeft + delta;
      let newRight = startRight - delta;

      if (newLeft < MIN_WIDTH) {
        newRight -= MIN_WIDTH - newLeft;
        newLeft = MIN_WIDTH;
      }
      if (newRight < MIN_WIDTH) {
        newLeft -= MIN_WIDTH - newRight;
        newRight = MIN_WIDTH;
      }

      leftCol.style.width = `${newLeft}px`;
      rightCol.style.width = `${newRight}px`;
    }

    function onUp() {
      document.body.classList.remove("col-resize-active");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      saveLocal(cols);
      setStatus(statusEl, "Изменения сохранены локально. Нажмите «Сохранить разметку», чтобы зафиксировать на сервере.", "info");
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  function collectWidths(cols) {
    const widths = {};
    cols.forEach((col) => {
      const key = col.dataset.col;
      if (!key) {
        return;
      }
      widths[key] = Math.round((parseFloat(col.style.width) || col.getBoundingClientRect().width) * 100) / 100;
    });
    return widths;
  }

  function applyWidths(cols, widths) {
    cols.forEach((col) => {
      const key = col.dataset.col;
      const value = widths[key];
      if (typeof value === "number" && value >= MIN_WIDTH) {
        col.style.width = `${value}px`;
      }
    });
  }

  function saveLocal(cols) {
    try {
      localStorage.setItem(LOCAL_KEY, JSON.stringify(collectWidths(cols)));
    } catch (_err) {
      /* ignore quota errors */
    }
  }

  function loadLocal() {
    try {
      const raw = localStorage.getItem(LOCAL_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_err) {
      return null;
    }
  }

  async function saveToServer(cols, statusEl, saveBtn) {
    const widths = collectWidths(cols);
    saveBtn.disabled = true;
    setStatus(statusEl, "Сохраняю на сервер…", "info");
    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ widths }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      saveLocal(cols);
      setStatus(
        statusEl,
        `Разметка сохранена на сервере (${payload.updated_at || "ok"}).`,
        "success",
      );
    } catch (err) {
      setStatus(statusEl, `Не удалось сохранить: ${err.message || err}`, "error");
    } finally {
      saveBtn.disabled = false;
    }
  }

  function setStatus(el, text, kind) {
    if (!el) {
      return;
    }
    el.textContent = text;
    el.dataset.state = kind || "info";
  }
})();
