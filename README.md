# Autoplius Scraper

Отдельный сервис для почасового сбора объявлений с [autoplius.lt](https://autoplius.lt/skelbimai/naudoti-automobiliai).

**Тестовый режим (по умолчанию):** сохраняет JSON-снимки локально в `data/`, без отправки в основной backend.

## Что собирает

- Первые **10 страниц** всех объявлений (`/skelbimai/naudoti-automobiliai`)
- Затем **детальные страницы** каждого объявления (`ENRICH_DETAILS=true`)
- Search: id, url, title, price, year, mileage, fuel, transmission, city, photo
- Detail: phone, VIN (masked), description, все параметры таблицы, галерея фото

~20 объявлений × 10 страниц ≈ **200 карточек/час** (+ ~200 detail-запросов).

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
| `SCRAPE_PAGES` | `10` | Сколько страниц поиска обходить |
| `ENRICH_DETAILS` | `true` | Заходить в каждое объявление за полной карточкой |
| `ENRICH_LIMIT` | `0` | Лимит detail-страниц (`0` = все) |
| `DETAIL_DELAY_SEC` | `2` | Пауза между detail-запросами |
| `PAGE_DELAY_SEC` | `3` | Пауза между страницами поиска |
| `SCRAPE_INTERVAL_HOURS` | `1` | Интервал для `scheduler.py` |
| `AUTO_CAPTCHA` | `true` | 2Captcha для Cloudflare Turnstile |
| `CAPTCHA_2CAPTCHA_API_KEY` | — | Ключ 2Captcha |
| `HEADLESS` | `true` | Headless Chrome |

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

## Хранение

- JSON-снимки: `data/latest.json`, `data/test/snapshots/...`
- SQLite: `data/autoplius.db` (таблицы `listings`, `scrape_runs`, `run_listings`)

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
