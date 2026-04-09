# StudyAssist Intel System

MVP-система для поиска площадок/конкурентов, сбора упоминаний, rule-based классификации, скоринга и постановки задач оператору.

## Что реализовано
- REST API для данных и операций (`/api/platforms`, `/api/mentions`, `/api/tasks`, `/api/run/discovery`, `/api/tasks/{id}/status`).
- GUI-дашборд оператора (`/`) с запуском discovery и сменой статуса задач.
- PostgreSQL/SQLite модель данных через SQLAlchemy ORM.
- MVP-пайплайн discovery -> mentions -> scoring -> tasks.
- Rule-based интент-классификатор и baseline scoring.
- Идемпотентность на уровне дедупа (`fingerprint`, `canonical URL`).
- Экспорты `CSV` через `scripts/export_csv.py`.

---

## Запуск на Windows 10 (БЕЗ Docker)

### 1) Установить Python 3.11+
Проверьте в PowerShell:
```powershell
python --version
```

### 2) Создать и активировать виртуальное окружение
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Установить зависимости
```powershell
pip install -e .[dev]
```

### 4) Подготовить конфиг
```powershell
copy .env.example .env
```
По умолчанию используется SQLite (`DATABASE_URL=sqlite:///./intel.db`), ничего дополнительно ставить не нужно.

### 5) Запустить GUI
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

После запуска:
- GUI: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

### 6) Запустить discovery и проверить данные
В GUI нажмите **Run discovery now**.

Или в PowerShell:
```powershell
python -c "from app.pipeline import run_discovery; print(run_discovery())"
```

### 7) Экспорт CSV
```powershell
python scripts/export_csv.py
```

---

## Операционный цикл через GUI
1. Открыть `/`.
2. Нажать **Run discovery now**.
3. Проверить новые platforms/mentions/tasks в таблицах.
4. Изменить статус задач в секции **Task status management**.

## Скрипты
### Linux/macOS
```bash
bash scripts/run_discovery.sh
bash scripts/run_trigger_scan.sh
bash scripts/run_gui.sh
python scripts/export_csv.py
pytest -q
```

### Windows (cmd)
```cmd
scripts\run_discovery.bat
scripts\run_trigger_scan.bat
scripts\run_gui.bat
python scripts\export_csv.py
pytest -q
```
