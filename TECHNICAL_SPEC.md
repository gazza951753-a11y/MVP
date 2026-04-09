# Техническое задание
## Автоматизированная система сбора и скоринга площадок и конкурентов для StudyAssist

## 1) Executive summary
Система предназначена для автоматизации разведки: поиск конкурентов и площадок, сбор и нормализация сигналов спроса, скоринг рисков и возможностей, постановка задач оператору.

### Ключевая идея MVP
Фокус — не на автоспаме и не на массовых публикациях, а на:
- автоматическом сборе и структурировании сигналов;
- приоритизации через scoring;
- подготовке безопасных ручных действий оператора.

### Результаты MVP
- Единый каталог сущностей: `competitors`, `platforms`, `mentions`, `triggers`, `tasks`.
- Автоматический расчёт `OpportunityScore`, `RiskScore`, `Confidence`.
- Очередь задач оператору с контекстом и рекомендацией.
- Экспорты в CSV/JSON/SQL и базовые интеграции.
- Метрики, логи, мониторинг ошибок, квот и блокировок.

---

## 2) Цели, KPI и границы

### 2.1 Цель системы
Реализовать воспроизводимый конвейер:
`discovery -> collection -> normalization -> classification -> scoring -> operator tasks -> analytics`.

### 2.2 Функциональные цели
Система должна:
1. Находить конкурентов и их публичные точки присутствия.
2. Находить площадки и упоминания по семантике и брендам конкурентов.
3. Извлекать правила площадок (если публичны).
4. Классифицировать интенты и тематику.
5. Считать `OpportunityScore` и `RiskScore`.
6. Создавать задачи оператору с контекстом, draft-текстом, UTM и чек-листом.

### 2.3 Нефункциональные цели
- Обработка rate limit (`HTTP 429`, `Retry-After`, exponential backoff).
- Полная трассируемость причин скоринга и источников данных.
- Идемпотентный ETL (повторный запуск не плодит дубликаты).
- Безопасное хранение секретов (только env/secrets manager).

### 2.4 В границы MVP НЕ входит
- Массовый автопостинг/автокомментарии/авторассылки.
- Автоматический обход CAPTCHA/антибот-защит.
- Сбор лишних персональных данных без операционной необходимости.

### 2.5 KPI пилота
| KPI | Определение | Цель пилота |
|---|---|---|
| Coverage: новые площадки | Новые `platforms/week` после дедупа | 50-200/нед |
| Precision shortlist | Доля годных площадок в топ-N | >= 60% |
| Time-to-task | `mentions.created_at -> tasks.created_at` | <= 60 мин |
| CAPTCHA/blocked rate | Доля блокировок/капч | <= 2-5% |
| API 429 rate | Контролируемый уровень 429 | без деградации SLA |
| Operator throughput | Закрытые задачи/день/оператор | 20-60 |
| Safety incidents | Жалобы/баны/ограничения | 0-минимум |

---

## 3) Архитектура и ETL

### 3.1 Компоненты
- **Orchestrator:** n8n/Airflow (расписания, DAG, ретраи).
- **Collectors:** Python-адаптеры API/HTML.
- **Storage:** PostgreSQL (OLTP + индексы + дедуп).
- **Queue:** Redis/RabbitMQ/SQS.
- **Processing/Scoring:** Python service (правила + фичи + scoring).
- **Operator UI:** Airtable/Notion/Web UI.
- **Observability:** Sentry + Prometheus.

### 3.2 Режимы запуска
- `Nightly discovery` — 1-2 раза в сутки.
- `Frequent trigger scan` — каждые 10-30 минут.
- `Revalidation cycle` — раз в 7-30 дней.

### 3.3 Политика retry/backoff
- Сеть: 3-5 ретраев + exponential backoff + jitter.
- `429`: уважать `Retry-After`, включать throttling/очереди.
- `4xx` (кроме 429): как правило без ретрая.
- `5xx`: ретраи.

### 3.4 CAPTCHA/blocked политика
При детекте challenge/CAPTCHA/403:
1. Остановить адаптер по источнику.
2. Создать task `investigate_access`.
3. Приложить HTML/screenshot и причину.
4. Дальнейшие варианты: официальный API / снижение частоты / ручной доступ / исключение источника.

---

## 4) Модель данных (PostgreSQL)

### 4.1 Основные таблицы
- `competitors`
- `platforms`
- `mentions`
- `triggers`
- `admin_contacts`
- `tasks`
- `users`
- `logs`

### 4.2 Ключевые требования к данным
- Дедуп по `canonical_url`, `handle`, `fingerprint`.
- Хранение `source_url` + `canonical_url`.
- Сырой payload (`raw_payload`) обязателен для аудита.
- В `logs` фиксировать `run_id`, `component`, `http_status`, `error_code`, payload.

---

## 5) Поиск, семантика и классификация

### 5.1 Базовые intent-кластеры
- `need_help`
- `urgent`
- `plagiarism`
- `formatting`
- `revisions`
- `competitor_mention`

### 5.2 Поисковые шаблоны
- `search_brand`: `"{brand}" OR "{brand_domain}"`
- `search_intent_ru`: запросы спроса (курсовая/диплом/срочно)
- `search_platform_tg`: `site:t.me (...)`
- `search_platform_vk`: `site:vk.com (...)`
- `search_rules`: `"{platform_url}" ("правила" OR "реклама запрещена")`
- `search_admin_contact`: `"{platform_name}" ("админ" OR "сотрудничество")`

### 5.3 Нормализация
- URL canonicalization (убрать UTM/ref, нормализовать host/scheme/slash).
- Нормализация текста (ru лемматизация, стоп-слова, словари синонимов).
- Выделение сущностей: бренды, тип работы, предмет/вуз.

---

## 6) Скоринг и принятие решений

### 6.1 Выходные метрики
- `OpportunityScore` (0..100)
- `RiskScore` (0..100)
- `Confidence` (0..1)

### 6.2 Baseline формулы
```text
OpportunityScore = clamp(
  0.30*RelevanceScore +
  0.20*DemandScore +
  0.15*FreshnessScore +
  0.10*AudienceScore +
  0.10*AdminReachabilityScore +
  0.10*CompetitorPresenceScore +
  0.05*ContentFitScore,
0..100)

RiskScore = clamp(
  0.35*RuleStrictnessScore +
  0.20*ModerationRiskScore +
  0.20*SpamSensitivityScore +
  0.10*AutomationBarrierScore +
  0.15*ReputationRiskScore,
0..100)
```

### 6.3 Пороговая логика
- `Opportunity >= 75` и `Risk <= 35` -> `reply_opportunity`
- `Opportunity >= 60` и `Risk <= 50` -> `review_platform`
- `Risk > 70` -> `watch_only`
- CAPTCHA/blocked -> `investigate_access`

---

## 7) Операционный workflow

### 7.1 Статусы задач
`new -> assigned -> in_review -> approved -> executed -> done`

Альтернативные ветки:
- `rejected`
- `risky`
- `needs_access`

### 7.2 Коммуникации
- `message_draft` хранится как черновик.
- Любая публикация/контакт только после ручного подтверждения оператора.
- Приоритет “экспертный ответ/запрос правил”, а не агрессивный sales-first сценарий.

### 7.3 UTM
Обязательные поля: `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`.
Рекомендуемый шаблон `utm_campaign`: `{platform_type}_{intent}_{YYYYMM}`.

---

## 8) Интеграции

### 8.1 Оркестрация
- n8n: cron + webhook workflows, метрики `/metrics`.
- Make: webhook ingress + контроль burst-лимитов.

### 8.2 Операторские доски
- Airtable (лимиты запросов и 429 policy).
- Notion (очередь и throttling, Retry-After).
- Google Sheets API (per-minute quotas + backoff).

### 8.3 Внутренние уведомления
- Telegram Bot API только для внутренних алертов и операционных событий.

---

## 9) Безопасность и комплаенс
- Политика “не спамить”: запрещена автоматическая массовая коммуникация.
- Строгое соблюдение лимитов площадок/API.
- Секреты только через env/secrets manager.
- Принцип минимизации данных.
- До касания площадки: проверка правил + подтверждение оператором.

---

## 10) Наблюдаемость и качество

### 10.1 Метрики
- `crawler_requests_total`
- `crawler_http_429_total`
- `crawler_blocked_total`
- `crawler_latency_seconds`
- `etl_runs_total`, `etl_run_duration_seconds`
- `tasks_created_total`, `tasks_closed_total`
- `task_cycle_time_seconds`
- `shortlist_precision`

### 10.2 Логирование
Минимальный контекст лога:
`run_id`, `component`, `event`, `url`, `http_status`, `error_code`, `message`, `payload`, `created_at`.

### 10.3 Sentry
Инициализируется early в lifecycle каждого сервиса (`collector`, `scorer`, `api`).

---

## 11) План работ
| Этап | Длительность | Результат | Приёмка |
|---|---|---|---|
| MVP | 2-4 недели | БД + seed-сбор + baseline scoring + tasks + exports | 200+ platforms, 30+ competitors, 100 tasks/нед |
| Пилот | 2-3 недели | Тюнинг весов, UTM-аналитика, улучшение dedupe | precision >= 60%, без safety-инцидентов |
| Расширение | 4-8 недель | Новые источники, optional ML intent, UI hardening | стабильный throughput + monitoring/alerts |

---

## 12) Рекомендуемая структура репозитория
```text
studyassist-intel-system/
  README.md
  docker-compose.yml
  .env.example
  pyproject.toml
  app/
    main.py
    config.py
    db/
      migrations/
      models.py
      schema.sql
    collectors/
      base.py
      search_templates.py
      sources/
        tg_catalog.py
        vk_public.py
        forums.py
    processing/
      normalize.py
      classify_rules.py
      scoring.py
      dedupe.py
    tasks/
      creator.py
      templates.py
    integrations/
      airtable.py
      notion.py
      google_sheets.py
      telegram_notify.py
    observability/
      sentry.py
      metrics.py
  scripts/
    run_discovery.sh
    run_trigger_scan.sh
    export_csv.py
```

---

## 13) Критерии приёмки MVP
1. Работает end-to-end цикл от discovery до постановки задач.
2. Есть дедуп и трассировка причин скоринга.
3. Есть ручной workflow без автоспама.
4. Экспорты CSV/NDJSON/SQL работают.
5. Включены логи, метрики, error tracking.
6. Идемпотентность подтверждена повторными прогонами.

## 14) Форматы экспорта
- `platforms.csv`
- `competitors.csv`
- `mentions.csv`
- `tasks.csv`
- `export/platforms.ndjson`
- `schema.sql`, `seed.sql`
