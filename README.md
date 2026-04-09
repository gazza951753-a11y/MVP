# StudyAssist Intel System

MVP-система для поиска площадок/конкурентов, сбора упоминаний, rule-based классификации, скоринга и постановки задач оператору.

## Что реализовано
- REST API для данных и операций (`/api/platforms`, `/api/mentions`, `/api/tasks`, `/api/run/discovery`, `/api/tasks/{id}/status`).
- GUI-дашборд оператора (`/`) с запуском discovery и сменой статуса задач.
- PostgreSQL-модель данных (ORM + `schema.sql`).
- MVP-пайплайн discovery -> mentions -> scoring -> tasks.
- Rule-based интент-классификатор и baseline scoring.
- Идемпотентность на уровне дедупа (`fingerprint`, `canonical URL`).
- Экспорты `CSV` через `scripts/export_csv.py`.
- Заготовки интеграций с retry/backoff для 429.

## Быстрый старт
```bash
docker compose up -d postgres
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

## Запуск GUI-приложения
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

После запуска:
- GUI: `http://localhost:8000/`
- Health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

## Операционный цикл через GUI
1. Открыть `/`.
2. Нажать **Run discovery now**.
3. Проверить новые platforms/mentions/tasks в таблицах.
4. Изменить статус задач в секции **Task status management**.

## Скрипты
```bash
bash scripts/run_discovery.sh
bash scripts/run_trigger_scan.sh
python scripts/export_csv.py
pytest -q
```
