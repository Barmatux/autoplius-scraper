# Autoplius Scraper

Отдельный сервис для сбора объявлений с [autoplius.lt](https://autoplius.lt/skelbimai/naudoti-automobiliai) (**каждые 30 минут**, инкрементально).

**Тестовый режим (по умолчанию):** сохраняет JSON-снимки локально в `data/`, без отправки в основной backend.

## Что собирает

- **Инкрементально (каждые 30 мин):** поиск с сортировкой «новые сверху», страницы пока не встретятся 2 подряд без новых ID vs SQLite; detail только для новых объявлений
- **Полный прогон (раз в 12 ч):** первые **10 страниц** (~200 объявлений), enrich всех
- Search: id, url, title, price (main + optional net/gross VAT), year, mileage, fuel, transmission, city, photo
- Detail: phone, VIN (masked), description, все параметры таблицы, галерея фото

## Быстрый старт

```powershell
cd autoplius-scraper
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

copy .env.example .env
# Заполнить CAPTCHA_2CAPTCHA_API_KEY в .env

# Первый запуск: Cloudflare может потребовать 1 solve (~30–60 сек).
# Cookies сохраняются в .browser-profile — следующие прогоны быстрее.

# Один прогон (2 страницы для проверки)
.\.venv\Scripts\python run_scrape.py --pages 2

# Полный прогон 10 страниц
.\.venv\Scripts\python run_scrape.py

# Планировщик: сразу + каждый час
.\.venv\Scripts\python scheduler.py
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TEST_MODE` | `true` | `true` → `data/test/snapshots/`, `false` → `data/prod/snapshots/` |
| `SCRAPE_PAGES` | `10` | Макс. страниц поиска (полный прогон; верхняя граница для incremental) |
| `INCREMENTAL_SCRAPE` | `true` | Останавливаться, когда новых ID vs БД нет |
| `INCREMENTAL_STOP_EMPTY_PAGES` | `2` | Сколько «пустых» страниц подряд до stop |
| `ENRICH_NEW_ONLY` | `true` | Detail только для объявлений без enrich в БД |
| `SEARCH_NEWEST_FIRST` | `true` | `order_by=3&order_direction=DESC` на Autoplius |
| `FULL_SCRAPE_INTERVAL_HOURS` | `12` | Как часто делать полный прогон 10 страниц |
| `ARCHIVE_REMOVED_ON_FULL_SCRAPE` | `true` | При полном прогоне помечать исчезнувшие объявления как `archived` |
| `ENRICH_DETAILS` | `true` | Заходить в каждое объявление за полной карточкой |
| `ENRICH_LIMIT` | `0` | Лимит detail-страниц (`0` = все) |
| `DETAIL_DELAY_SEC` | `2` | Пауза между detail-запросами |
| `PAGE_DELAY_SEC` | `3` | Пауза между страницами поиска |
| `SCRAPE_INTERVAL_HOURS` | `1` | Интервал для `scheduler.py` |
| `AUTO_CAPTCHA` | `true` | 2Captcha для Cloudflare Turnstile |
| `CAPTCHA_2CAPTCHA_API_KEY` | — | Ключ 2Captcha |
| `HEADLESS` | `true` | Headless Chrome |
| `SYNC_PHOTOS_AFTER_SCRAPE` | `true` | Upload photos to MinIO after each run (current run only) |
| `SYNC_PHOTOS_TIMEOUT_SEC` | `25` | HTTP timeout for photo download |
| `AUTOPLIUS_BASE_URL` | `https://ru.autoplius.lt` | Russian Autoplius source |
| `TRANSLATE_DESCRIPTIONS` | `true` | Translate seller descriptions to Russian |
| `TRANSLATE_DELAY_SEC` | `0.15` | Pause between translation API calls |

## Выходные файлы

```
data/
  latest.json              # последний снимок (для diff)
  last_run.json            # метаданные последнего прогона
  test/snapshots/YYYY-MM-DD/YYYYMMDDTHHMMSSZ.json
logs/
  scraper.log
```

## Деплой на отдельную VM (systemd)

```bash
sudo useradd -r -m -d /var/lib/autoplius-scraper autoplius
sudo mkdir -p /opt/autoplius-scraper /var/log/autoplius-scraper
sudo chown -R autoplius:autoplius /opt/autoplius-scraper /var/lib/autoplius-scraper /var/log/autoplius-scraper

# Скопировать проект, создать .venv, pip install -r requirements.txt
sudo cp deploy/autoplius-scraper.service deploy/autoplius-scraper.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now autoplius-scraper.timer
sudo systemctl start autoplius-scraper.service
```

### Обновление на VM (только через git)

**Источник правды — `origin/main`.** Не копируйте файлы через `scp`, кроме аварийных случаев.

**Локально (перед деплоем):**

```bash
git fetch origin main
git pull --no-rebase origin main   # или rebase, если так принято в ветке
# ... правки, commit ...
git push origin HEAD
```

**На VM:**

```bash
ssh romanshleg@84.252.139.137
sudo bash /opt/autoplius-scraper/deploy/deploy-from-git.sh
```

Скрипт делает `git fetch` + `git pull --ff-only origin main`, `pip install`, обновляет systemd unit-файлы и перезапускает UI. Scraper-таймер подхватит новый код на следующем запуске.

После деплоя, чтобы убрать уже сохранённые Ligier/Microcar из базы:

```bash
sudo -u autoplius /opt/autoplius-scraper/.venv/bin/python tools/purge_blocked_makes.py
```

Если `pull --ff-only` не проходит (локальные правки на VM) — разберите drift вручную; не делайте `reset --hard` без необходимости.

## Хранение

- JSON-снимки: `data/latest.json`, `data/test/snapshots/...`
- SQLite: `data/autoplius.db` (таблицы `listings`, `scrape_runs`, `run_listings`)

### Синхронизация объявлений (как av.by)

- **Merge, не replace:** при обновлении поля сливаются; не перезаписываются `first_seen_at`, `description_ru`, `phone`, `vin_masked` (если уже есть).
- **Detail:** если в БД уже есть enrich, а текущий прогон — только search preview, detail-поля сохраняются.
- **Архив:** при **полном** прогоне объявления из предыдущего снимка, которых нет в текущем каталоге (~10 страниц), получают `status=archived`. При повторном появлении на Autoplius снова становятся `active`.
- **Инкрементальный прогон** не архивирует — только добавляет/обновляет видимые объявления.
- **Цены с/без НДС:** парсятся основная цена и подпись `.list-price-subtitle` (`be PVM`, `su PVM`); в БД `price_eur`, `price_net_eur`, `price_gross_eur`, `price_vat_note`.

Импорт всех существующих JSON в БД:

```powershell
.\.venv\Scripts\python import_to_db.py
```

UI по умолчанию читает из SQLite (если файл есть).

## UI результатов

Простой веб-интерфейс для просмотра снимков:

```powershell
.\.venv\Scripts\pip install flask
$env:DATA_DIR = "data"
.\.venv\Scripts\python -m ui.app
# http://127.0.0.1:8080
```

На VM сервис `autoplius-ui.service` слушает порт **8080**.

## Docker

```bash
docker build -t autoplius-scraper .
docker run --env-file .env -v autoplius-data:/app/data autoplius-scraper
```
