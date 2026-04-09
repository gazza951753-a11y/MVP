# Implementation Plan (после утверждения ТЗ)

## Этап 0 — Подготовка (1-2 дня)
- [ ] Утвердить стек и владельцев (Backend/Data/Operator/DevOps).
- [ ] Создать backlog в трекере (epic + tasks).
- [ ] Определить seed-источники для первой итерации (2-3 источника).

## Этап 1 — Data Foundation (3-5 дней)
**Цель:** получить стабильный слой хранения и дедуп.

### Задачи
- [ ] Создать `schema.sql` с таблицами из `TECHNICAL_SPEC.md`.
- [ ] Добавить индексы:
  - `platforms(url)` unique
  - `mentions(fingerprint)` index
  - `logs(created_at, component, http_status)`
- [ ] Добавить миграции (Alembic).
- [ ] Реализовать нормализацию canonical URL.
- [ ] Реализовать fingerprint (sha256 по нормализованному тексту + source_url).

### Definition of Done
- [ ] Повторный запуск импорта не создаёт дубли.
- [ ] Есть SQL-скрипт для локального старта.

## Этап 2 — Collectors MVP (4-6 дней)
**Цель:** получать первые `platforms` и `mentions` автоматически.

### Задачи
- [ ] Реализовать `Collector` базовый интерфейс.
- [ ] Реализовать 1 discovery-адаптер.
- [ ] Реализовать 1 mention-адаптер.
- [ ] Добавить retry policy (429/5xx/backoff+jitter).
- [ ] Добавить `investigate_access` при CAPTCHA/blocked.

### Definition of Done
- [ ] По расписанию создаются записи в `platforms` и `mentions`.
- [ ] Ошибки и 429 фиксируются в `logs`.

## Этап 3 — Processing + Scoring (3-5 дней)
**Цель:** получать приоритезированные задачи для оператора.

### Задачи
- [ ] Rule-based intents (`need_help`, `urgent`, `plagiarism` и т.д.).
- [ ] Рассчёт `OpportunityScore`, `RiskScore`, `Confidence`.
- [ ] Threshold-логика создания `tasks`.
- [ ] Шаблоны `message_draft` + UTM generator.

### Definition of Done
- [ ] Минимум 100 задач/неделю в тестовом контуре.
- [ ] Есть объяснимость: какие триггеры сработали.

## Этап 4 — Operator Loop + Exports (2-4 дня)
**Цель:** замкнуть ручной цикл проверки и обратной связи.

### Задачи
- [ ] Экспорт `platforms.csv`, `mentions.csv`, `tasks.csv`.
- [ ] Интеграция с Airtable/Notion (одна на выбор в MVP).
- [ ] Статусы workflow: `new -> assigned -> in_review -> approved/rejected/risky`.

### Definition of Done
- [ ] Оператор закрывает задачи в доске.
- [ ] Есть поле `reviewer_verdict` для обучения и контроля качества.

## Этап 5 — Observability + Pilot (3-5 дней)
**Цель:** стабилизировать и измерять систему.

### Задачи
- [ ] Sentry SDK для collector/scoring/API.
- [ ] Prometheus метрики по запросам/429/latency/task cycle.
- [ ] Дашборд по KPI пилота.

### Definition of Done
- [ ] Видно p95 latency, 429 rate, shortlist precision.
- [ ] Подготовлен runbook инцидентов (429 spikes, blocked sources).

---

## Приоритеты на ближайшие 7 дней
1. DDL + миграции + дедуп (самый высокий приоритет).
2. Один стабильный collector + корректная обработка 429.
3. Rule-based intents + baseline scoring.
4. Автосоздание задач и экспорт CSV для оператора.

## Риски и как снизить
- **Риск:** блокировки источников.
  - **Митигация:** меньше частота, respect `Retry-After`, переход на API.
- **Риск:** много шума в mentions.
  - **Митигация:** negative keywords, ручная валидация top-N.
- **Риск:** медленный операционный цикл.
  - **Митигация:** приоритизация только top-score + clear templates.
