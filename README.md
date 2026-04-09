# StudyAssist Intel System

MVP-система для поиска площадок/конкурентов, сбора упоминаний, rule-based классификации, скоринга и постановки задач оператору.

## Что важно в текущей версии
- Интерфейс оператора на русском языке.
- Поиск выполняется в сети: сбор идёт из Рунета по тематическим RU-запросам.
- Поддержан запуск без Docker на Windows 10 (SQLite по умолчанию).

## Функции
- REST API: `/api/platforms`, `/api/mentions`, `/api/tasks`, `/api/run/discovery`, `/api/tasks/{id}/status`.
- GUI-дашборд (`/`) с кнопкой **Запустить поиск по Рунету** и управлением статусами задач.
- Коллектор `RussianWebCollector`, который делает онлайн-поиск по RU-запросам и извлекает площадки/упоминания.
- Пайплайн: discovery -> normalize -> classify -> score -> task.

---

## Запуск на Windows 10 без Docker

### 1) Python
```powershell
python --version
```

### 2) Виртуальное окружение
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Установка
```powershell
pip install -e .[dev]
copy .env.example .env
```

### 4) Запуск сервера
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

После запуска:
- GUI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

---

## Как сделать доступ из сети (не только локально)

### Вариант A: Белый IP / VPS
1. Запустить приложение на сервере: `--host 0.0.0.0`.
2. Открыть порт 8000 в firewall.
3. Настроить reverse proxy (Nginx/Caddy) + HTTPS.

### Вариант B: Быстрый туннель для демонстрации
- `cloudflared tunnel --url http://localhost:8000`
- или `ngrok http 8000`

После этого GUI/API будут доступны по публичной HTTPS-ссылке.

---

## Проверка работы поиска по Рунету
1. Открыть GUI `/`.
2. Нажать **Запустить поиск по Рунету**.
3. Убедиться, что в таблицах появляются ссылки на внешние источники (`t.me`, `vk.com`, форумы/сайты).

CLI-альтернатива:
```powershell
python -c "from app.pipeline import run_discovery; print(run_discovery())"
python scripts/export_csv.py
```

## Скрипты
### Windows (cmd)
```cmd
scripts\run_discovery.bat
scripts\run_trigger_scan.bat
scripts\run_gui.bat
```

### Linux/macOS
```bash
bash scripts/run_discovery.sh
bash scripts/run_trigger_scan.sh
bash scripts/run_gui.sh
```
