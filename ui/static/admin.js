document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) {
    return;
  }
  const isArchive = form.classList.contains("admin-archive-form");
  const isRestore = form.classList.contains("admin-restore-form");
  if (!isArchive && !isRestore) {
    return;
  }

  const message = isArchive
    ? "Отправить объявление в архив? Оно исчезнет из публичной выдачи."
    : "Вернуть объявление в активную выдачу?";
  if (!window.confirm(message)) {
    event.preventDefault();
    return;
  }

  const button = form.querySelector('button[type="submit"]');
  if (!(button instanceof HTMLButtonElement)) {
    return;
  }
  button.disabled = true;
  button.textContent = isArchive ? "В архив…" : "Возврат…";
});
