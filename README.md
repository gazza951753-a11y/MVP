# StudyAssist Intel System

MVP-система для поиска площадок/конкурентов, сбора упоминаний, rule-based классификации, скоринга и постановки задач оператору.

## Что реализовано в этом репозитории
- FastAPI API (`/health`, `/run/discovery`).
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

Запуск API:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Запуск discovery:
```bash
bash scripts/run_discovery.sh
```

Экспорт данных:
```bash
python scripts/export_csv.py
```

Тесты:
```bash
pytest -q
```

## Структура
- `app/main.py` — API и healthchecks.
- `app/pipeline.py` — ETL MVP.
- `app/db/models.py` — сущности БД.
- `app/processing/*` — нормализация/классификация/скоринг/дедуп.
- `app/tasks/*` — принятие решения и генерация task payload.
- `scripts/*` — operational scripts.
