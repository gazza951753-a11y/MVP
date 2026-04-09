from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import Mention, Platform, Task
from app.pipeline import run_discovery

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


def _render_table(rows: list[dict], columns: list[str]) -> str:
    headers = "".join(f"<th>{c}</th>" for c in columns)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{row.get(c, '')}</td>" for c in columns) + "</tr>"
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"


@router.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    with SessionLocal() as session:
        platforms = session.execute(select(Platform).order_by(Platform.created_at.desc()).limit(30)).scalars().all()
        mentions = session.execute(select(Mention).order_by(Mention.collected_at.desc()).limit(30)).scalars().all()
        tasks = session.execute(select(Task).order_by(Task.created_at.desc()).limit(50)).scalars().all()

    platform_rows = [
        {
            "title": p.title,
            "platform_type": p.platform_type,
            "url": p.url,
            "audience_size": p.audience_size or 0,
        }
        for p in platforms
    ]
    mention_rows = [
        {
            "source_url": m.source_url,
            "text": (m.text or "")[:120],
            "intents": ", ".join(m.detected_intents),
        }
        for m in mentions
    ]
    task_rows = [
        {
            "id": str(t.id),
            "type": t.task_type,
            "status": t.status,
            "priority": t.priority,
            "opportunity": t.opportunity_score,
            "risk": t.risk_score,
        }
        for t in tasks
    ]

    task_update_rows = ""
    for t in tasks:
        options = "".join(
            f"<option value='{status}' {'selected' if status == t.status else ''}>{status}</option>"
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
              <button type='submit'>Save</button>
            </form>
          </td>
        </tr>
        """

    return f"""
<!doctype html>
<html lang='ru'>
<head>
  <meta charset='utf-8'>
  <title>StudyAssist Intel GUI</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1, h2 {{ margin: 8px 0; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f2f2f2; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; }}
    .actions {{ margin: 12px 0 20px; }}
    button {{ padding: 8px 12px; cursor: pointer; }}
  </style>
</head>
<body>
  <h1>StudyAssist Intel — Operator GUI</h1>
  <div class='actions'>
    <form method='post' action='/gui/run-discovery'>
      <button type='submit'>Run discovery now</button>
    </form>
  </div>

  <div class='row'>
    <div class='card'>
      <h2>Platforms (latest 30)</h2>
      {_render_table(platform_rows, ['title', 'platform_type', 'url', 'audience_size'])}
    </div>
    <div class='card'>
      <h2>Mentions (latest 30)</h2>
      {_render_table(mention_rows, ['source_url', 'text', 'intents'])}
    </div>
  </div>

  <div class='card'>
    <h2>Tasks (latest 50)</h2>
    {_render_table(task_rows, ['id', 'type', 'status', 'priority', 'opportunity', 'risk'])}
  </div>

  <div class='card'>
    <h2>Task status management</h2>
    <table>
      <thead>
        <tr>
          <th>Task ID</th><th>Type</th><th>Priority</th><th>Opportunity</th><th>Risk</th><th>Status</th>
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
    run_discovery()
    return RedirectResponse(url="/", status_code=303)


@router.post("/gui/task-status")
def update_task_status_gui(task_id: str = Form(...), status: str = Form(...)) -> RedirectResponse:
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task and status in STATUS_OPTIONS:
            task.status = status
            session.add(task)
            session.commit()
    return RedirectResponse(url="/", status_code=303)
