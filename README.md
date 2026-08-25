# Autoplius Scraper

Отдельный сервис для почасового сбора объявлений с [autoplius.lt](https://autoplius.lt/skelbimai/naudoti-automobiliai).

**Тестовый режим (по умолчанию):** сохраняет JSON-снимки локально в `data/`, без отправки в основной backend.

## Что собирает

- Первые **10 страниц** всех объявлений (`/skelbimai/naudoti-automobiliai`, без фильтра по марке)
- ~20 объявлений на страницу → **~200 уникальных карточек** за прогон
- Поля: id, url, title, price, year, mileage, fuel, transmission, city, photo

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
| `PAGE_DELAY_SEC` | `3` | Пауза между страницами |
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

## Docker

```bash
docker build -t autoplius-scraper .
docker run --env-file .env -v autoplius-data:/app/data autoplius-scraper
```
