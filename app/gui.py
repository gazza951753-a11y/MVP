from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import Mention, Platform, Task
from app.pipeline import clear_runtime_data, run_discovery

router = APIRouter(tags=["gui"])

STATUS_OPTIONS = [
    "new",
    "assigned",
    "in_review",
    "approved",
    "executed",
    "rejected",
    "risky",
    "needs_access",
    "done",
]

STATUS_RU = {
    "new": "Новая",
    "assigned": "Назначена",
    "in_review": "На проверке",
    "approved": "Одобрена",
    "executed": "Выполнена",
    "rejected": "Отклонена",
    "risky": "Рискованная",
    "needs_access": "Нужен доступ",
    "done": "Закрыта",
}


def _render_table(rows: list[dict], columns: list[str]) -> str:
    headers = "".join(f"<th>{c}</th>" for c in columns)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{row.get(c, '')}</td>" for c in columns) + "</tr>"
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> str:
    info = request.query_params.get("info")

    with SessionLocal() as session:
        platforms = session.execute(select(Platform).order_by(Platform.created_at.desc()).limit(30)).scalars().all()
        mentions = session.execute(select(Mention).order_by(Mention.collected_at.desc()).limit(30)).scalars().all()
        tasks = session.execute(select(Task).order_by(Task.created_at.desc()).limit(50)).scalars().all()

    platform_rows = [
        {
            "Название": p.title,
            "Тип": p.platform_type,
            "Ссылка": p.url,
            "Аудитория": p.audience_size or 0,
        }
        for p in platforms
    ]
    mention_rows = [
        {
            "Источник": m.source_url,
            "Текст": (m.text or "")[:120],
            "Интенты": ", ".join(m.detected_intents),
        }
        for m in mentions
    ]
    task_rows = [
        {
            "ID": str(t.id),
            "Тип": t.task_type,
            "Статус": STATUS_RU.get(t.status, t.status),
            "Приоритет": t.priority,
            "Opportunity": t.opportunity_score,
            "Risk": t.risk_score,
        }
        for t in tasks
    ]

    task_update_rows = ""
    for t in tasks:
        options = "".join(
            f"<option value='{status}' {'selected' if status == t.status else ''}>{STATUS_RU.get(status, status)}</option>"
            for status in STATUS_OPTIONS
        )
        task_update_rows += f"""
        <tr>
          <td>{t.id}</td>
          <td>{t.task_type}</td>
          <td>{t.priority}</td>
          <td>{t.opportunity_score}</td>
          <td>{t.risk_score}</td>
          <td>
            <form method='post' action='/gui/task-status'>
              <input type='hidden' name='task_id' value='{t.id}' />
              <select name='status'>{options}</select>
              <button type='submit'>Сохранить</button>
            </form>
          </td>
        </tr>
        """

    info_block = f"<div class='info'>{info}</div>" if info else ""

    return f"""
<!doctype html>
<html lang='ru'>
<head>
  <meta charset='utf-8'>
  <title>StudyAssist — панель оператора</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1, h2 {{ margin: 8px 0; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f2f2f2; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; }}
    .actions {{ margin: 12px 0 20px; display: flex; gap: 12px; }}
    .hint {{ color: #333; margin-top: 5px; }}
    .info {{ background:#eef7ff; border:1px solid #cfe6ff; padding:10px; margin:10px 0; border-radius:6px; }}
    button {{ padding: 8px 12px; cursor: pointer; }}
  </style>
</head>
<body>
  <h1>StudyAssist Intel — панель оператора</h1>
  <p class='hint'>Если в таблицах 1 строка, скорее всего это старые демо-данные. Нажмите «Очистить демо-данные», потом «Запустить поиск по Рунету».</p>
  {info_block}

  <div class='actions'>
    <form method='post' action='/gui/run-discovery'>
      <button type='submit'>Запустить поиск по Рунету</button>
    </form>
    <form method='post' action='/gui/clear'>
      <button type='submit'>Очистить демо-данные</button>
    </form>
  </div>

  <div class='row'>
    <div class='card'>
      <h2>Площадки (последние 30)</h2>
      {_render_table(platform_rows, ['Название', 'Тип', 'Ссылка', 'Аудитория'])}
    </div>
    <div class='card'>
      <h2>Упоминания (последние 30)</h2>
      {_render_table(mention_rows, ['Источник', 'Текст', 'Интенты'])}
    </div>
  </div>

  <div class='card'>
    <h2>Задачи (последние 50)</h2>
    {_render_table(task_rows, ['ID', 'Тип', 'Статус', 'Приоритет', 'Opportunity', 'Risk'])}
  </div>

  <div class='card'>
    <h2>Управление статусами задач</h2>
    <table>
      <thead>
        <tr>
          <th>ID задачи</th><th>Тип</th><th>Приоритет</th><th>Opportunity</th><th>Risk</th><th>Статус</th>
        </tr>
      </thead>
      <tbody>{task_update_rows}</tbody>
    </table>
  </div>
</body>
</html>
    """


@router.post("/gui/run-discovery")
def run_discovery_gui() -> RedirectResponse:
    result = run_discovery()
    info = (
        f"Найдено площадок: {result['platforms_seen']}, упоминаний: {result['mentions_seen']}, "
        f"создано задач: {result['tasks_created']}."
    )
    if result.get("warning"):
        info += f" Внимание: {result['warning']}"
    return RedirectResponse(url=f"/?info={info}", status_code=303)


@router.post("/gui/clear")
def clear_gui() -> RedirectResponse:
    result = clear_runtime_data()
    info = (
        f"Удалено: площадок={result['platforms_deleted']}, "
        f"упоминаний={result['mentions_deleted']}, задач={result['tasks_deleted']}"
    )
    return RedirectResponse(url=f"/?info={info}", status_code=303)


@router.post("/gui/task-status")
def update_task_status_gui(task_id: str = Form(...), status: str = Form(...)) -> RedirectResponse:
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task and status in STATUS_OPTIONS:
            task.status = status
            session.add(task)
            session.commit()
    return RedirectResponse(url="/", status_code=303)
