"""Operator dashboard — web UI served by FastAPI, wrapped by pywebview on desktop."""
from __future__ import annotations

import json
import os
from pathlib import Path

import threading

from fastapi import APIRouter, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select

from app.db.base import SessionLocal, _db_url
from app.db.models import Mention, Platform, Task
from app.pipeline import run_discovery, run_trigger_scan

router = APIRouter(tags=["gui"])

STATUS_OPTIONS = [
    "new", "assigned", "in_review", "approved",
    "executed", "rejected", "risky", "needs_access", "done",
]

_SCORE_THRESHOLDS = {
    "opp": {"high": 75, "mid": 55},
    "risk": {"high": 60, "mid": 40},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opp_class(score: float) -> str:
    if score >= _SCORE_THRESHOLDS["opp"]["high"]:
        return "score-high"
    if score >= _SCORE_THRESHOLDS["opp"]["mid"]:
        return "score-mid"
    return "score-low"


def _risk_class(score: float) -> str:
    if score >= _SCORE_THRESHOLDS["risk"]["high"]:
        return "score-danger"
    if score >= _SCORE_THRESHOLDS["risk"]["mid"]:
        return "score-warn"
    return "score-ok"


def _badge(text: str, cls: str = "") -> str:
    return f"<span class='badge {cls}'>{text}</span>"


def _settings_path() -> Path:
    raw = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(raw) / "StudyAssist" / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_settings() -> dict:
    p = _settings_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_settings(data: dict) -> None:
    _settings_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTML skeleton
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg: #f5f7fa;
  --sidebar-bg: #1a2236;
  --sidebar-text: #c8d4e8;
  --sidebar-active: #3b82f6;
  --card-bg: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --text-muted: #64748b;
  --primary: #3b82f6;
  --primary-dark: #2563eb;
  --success: #10b981;
  --warn: #f59e0b;
  --danger: #ef4444;
  --radius: 8px;
  --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { display: flex; height: 100vh; font-family: 'Segoe UI', system-ui, sans-serif;
       background: var(--bg); color: var(--text); font-size: 14px; overflow: hidden; }

/* Sidebar */
#sidebar { width: 220px; min-width: 220px; background: var(--sidebar-bg);
           display: flex; flex-direction: column; padding: 0; overflow: hidden; }
#sidebar .logo { padding: 20px 18px 16px; border-bottom: 1px solid rgba(255,255,255,.07); }
#sidebar .logo span { font-size: 16px; font-weight: 700; color: #fff; display: block; }
#sidebar .logo small { font-size: 11px; color: var(--sidebar-text); opacity: .6; }
#sidebar nav { flex: 1; padding: 10px 0; overflow-y: auto; }
#sidebar nav a { display: flex; align-items: center; gap: 10px; padding: 10px 18px;
                 color: var(--sidebar-text); text-decoration: none; font-size: 13.5px;
                 border-left: 3px solid transparent; transition: all .15s; }
#sidebar nav a:hover { background: rgba(255,255,255,.06); color: #fff; }
#sidebar nav a.active { background: rgba(59,130,246,.15); color: #fff;
                        border-left-color: var(--sidebar-active); }
#sidebar nav a .icon { font-size: 16px; width: 20px; text-align: center; }
#sidebar .sidebar-bottom { padding: 12px 18px; border-top: 1px solid rgba(255,255,255,.07);
                            font-size: 11px; color: var(--sidebar-text); opacity: .5; }

/* Main */
#main { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
#topbar { background: var(--card-bg); border-bottom: 1px solid var(--border);
          padding: 12px 24px; display: flex; align-items: center; gap: 12px;
          position: sticky; top: 0; z-index: 10; box-shadow: var(--shadow); }
#topbar h1 { font-size: 16px; font-weight: 600; flex: 1; }
#content { padding: 24px; flex: 1; }

/* Cards */
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius);
        padding: 18px 20px; margin-bottom: 20px; box-shadow: var(--shadow); }
.card h2 { font-size: 14px; font-weight: 600; color: var(--text-muted); text-transform: uppercase;
           letter-spacing: .5px; margin-bottom: 14px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }

/* Stats */
.stat-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius);
             padding: 16px 20px; box-shadow: var(--shadow); }
.stat-card .val { font-size: 28px; font-weight: 700; color: var(--primary); }
.stat-card .lbl { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

/* Tables */
.tbl-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th { background: var(--bg); font-size: 12px; font-weight: 600; color: var(--text-muted);
     text-transform: uppercase; letter-spacing: .4px; padding: 8px 12px; text-align: left;
     border-bottom: 2px solid var(--border); white-space: nowrap; }
td { padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
tr:last-child td { border-bottom: 0; }
tr:hover td { background: #f8fafc; }
.url-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.text-cell { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Scores */
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px;
         font-weight: 600; white-space: nowrap; }
.score-high { background: #d1fae5; color: #065f46; }
.score-mid  { background: #fef9c3; color: #854d0e; }
.score-low  { background: #f1f5f9; color: var(--text-muted); }
.score-ok     { background: #d1fae5; color: #065f46; }
.score-warn   { background: #fef9c3; color: #854d0e; }
.score-danger { background: #fee2e2; color: #991b1b; }
.badge.status-new     { background: #e0f2fe; color: #0369a1; }
.badge.status-approved{ background: #d1fae5; color: #065f46; }
.badge.status-risky   { background: #fee2e2; color: #991b1b; }
.badge.status-done    { background: #f1f5f9; color: var(--text-muted); }

/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border: none;
       border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500;
       text-decoration: none; transition: opacity .15s; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-dark); }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--text); }
.btn-ghost:hover { background: var(--bg); }

/* Forms / inputs */
select, input[type=text], input[type=password], input[type=number], textarea {
  border: 1px solid var(--border); border-radius: 6px; padding: 7px 10px;
  font-size: 13px; width: 100%; background: var(--card-bg); color: var(--text); }
select:focus, input:focus, textarea:focus { outline: 2px solid var(--primary); border-color: transparent; }
label { font-size: 13px; font-weight: 500; color: var(--text-muted); display: block; margin-bottom: 5px; }
.form-row { margin-bottom: 16px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

/* Flash */
.flash { padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; }
.flash.ok { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
.flash.err { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }

/* Priority pill */
.prio-1 { color: var(--text-muted); }
.prio-2 { color: var(--warn); }
.prio-3 { color: var(--warn); font-weight: 600; }
.prio-4 { color: var(--danger); font-weight: 700; }
.prio-5 { color: var(--danger); font-weight: 800; }

/* Loading spinner */
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,.3);
           border-top-color: #fff; border-radius: 50%; animation: spin .6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
"""

_SIDEBAR_NAV = """
<div id="sidebar">
  <div class="logo">
    <span>&#128269; StudyAssist Intel</span>
    <small>operator dashboard</small>
  </div>
  <nav>
    <a href="/" class="{d}"><span class="icon">&#128202;</span> Дашборд</a>
    <a href="/platforms" class="{p}"><span class="icon">&#127760;</span> Площадки</a>
    <a href="/tasks" class="{t}"><span class="icon">&#9989;</span> Задачи</a>
    <a href="/mentions" class="{m}"><span class="icon">&#128172;</span> Упоминания</a>
    <a href="/settings" class="{s}"><span class="icon">&#9881;&#65039;</span> Настройки</a>
  </nav>
  <div class="sidebar-bottom">v0.3.0 · SQLite/PG</div>
</div>
"""


def _page(title: str, body: str, active: str = "d", flash: str = "") -> str:
    nav = _SIDEBAR_NAV.format(
        d="active" if active == "d" else "",
        p="active" if active == "p" else "",
        t="active" if active == "t" else "",
        m="active" if active == "m" else "",
        s="active" if active == "s" else "",
    )
    flash_html = f"<div class='flash ok'>{flash}</div>" if flash else ""
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{title} — StudyAssist Intel</title>
  <style>{_CSS}</style>
</head>
<body>
{nav}
<div id="main">
  <div id="topbar">
    <h1>{title}</h1>
    <form method="post" action="/gui/run-discovery" id="disco-form">
      <button class="btn btn-primary btn-sm" type="submit" onclick="this.innerHTML='<span class=spinner></span> Запуск…';this.disabled=true">
        &#9654; Запустить Discovery
      </button>
    </form>
    <a href="/gui/trigger-scan" class="btn btn-ghost btn-sm">&#8635; Триггер-скан</a>
  </div>
  <div id="content">
    {flash_html}
    {body}
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def dashboard(flash: str = "") -> str:
    with SessionLocal() as session:
        n_platforms = session.execute(select(func.count()).select_from(Platform)).scalar() or 0
        n_tasks = session.execute(select(func.count()).select_from(Task)).scalar() or 0
        n_mentions = session.execute(select(func.count()).select_from(Mention)).scalar() or 0
        n_open = session.execute(
            select(func.count()).select_from(Task).where(Task.status.in_(["new", "assigned", "in_review"]))
        ).scalar() or 0

        top_tasks = session.execute(
            select(Task, Platform)
            .join(Platform, Task.platform_id == Platform.id)
            .where(Task.status.in_(["new", "assigned", "in_review"]))
            .order_by(Task.opportunity_score.desc(), Task.risk_score.asc())
            .limit(10)
        ).all()

    stats = f"""
    <div class="grid-4">
      <div class="stat-card"><div class="val">{n_platforms}</div><div class="lbl">Площадок</div></div>
      <div class="stat-card"><div class="val">{n_mentions}</div><div class="lbl">Упоминаний</div></div>
      <div class="stat-card"><div class="val">{n_tasks}</div><div class="lbl">Задач всего</div></div>
      <div class="stat-card"><div class="val" style="color:var(--warn)">{n_open}</div><div class="lbl">Открытых задач</div></div>
    </div>"""

    rows = ""
    for task, plat in top_tasks:
        rows += f"""<tr>
          <td><a href="/tasks">{_badge(task.task_type, 'status-' + task.status)}</a></td>
          <td class="prio-{task.priority}">{task.priority}</td>
          <td>{_badge(f'{task.opportunity_score:.0f}', _opp_class(task.opportunity_score))}</td>
          <td>{_badge(f'{task.risk_score:.0f}', _risk_class(task.risk_score))}</td>
          <td class="url-cell"><a href="{plat.url}" target="_blank">{plat.title}</a></td>
          <td class="text-cell">{task.recommended_action or ''}</td>
        </tr>"""

    table = f"""
    <div class="card">
      <h2>&#128203; Топ задач для обработки</h2>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Тип</th><th>Приор.</th><th>Opp</th><th>Risk</th><th>Площадка</th><th>Рекомендация</th></tr></thead>
          <tbody>{rows or '<tr><td colspan=6 style="color:var(--text-muted);text-align:center">Нет открытых задач</td></tr>'}</tbody>
        </table>
      </div>
    </div>"""

    return _page("Дашборд", stats + table, active="d", flash=flash)


# ---------------------------------------------------------------------------
# Platforms
# ---------------------------------------------------------------------------

@router.get("/platforms", response_class=HTMLResponse)
def platforms_page() -> str:
    with SessionLocal() as session:
        rows_db = session.execute(
            select(Platform).order_by(Platform.created_at.desc()).limit(200)
        ).scalars().all()

    rows = ""
    for p in rows_db:
        rows += f"""<tr>
          <td class="url-cell" title="{p.url}"><a href="{p.url}" target="_blank">{p.title}</a></td>
          <td>{_badge(p.platform_type)}</td>
          <td>{p.audience_size or '—'}</td>
          <td><span class="prio-{p.commercial_tolerance+1}">{p.commercial_tolerance}/5</span></td>
          <td class="text-cell">{(p.tags or [])}</td>
          <td style="color:var(--text-muted);font-size:11px">{p.discovery_source}</td>
        </tr>"""

    body = f"""<div class="card">
      <h2>&#127760; Площадки (последние 200)</h2>
      <div class="tbl-wrap"><table>
        <thead><tr><th>Название / URL</th><th>Тип</th><th>Аудитория</th><th>Толерантность</th><th>Теги</th><th>Источник</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=6 style="text-align:center;color:var(--text-muted)">Нет данных — запустите Discovery</td></tr>'}</tbody>
      </table></div></div>"""
    return _page("Площадки", body, active="p")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(flash: str = "") -> str:
    with SessionLocal() as session:
        rows_db = session.execute(
            select(Task, Platform)
            .join(Platform, Task.platform_id == Platform.id)
            .order_by(Task.opportunity_score.desc(), Task.risk_score.asc())
            .limit(100)
        ).all()

    rows = ""
    for task, plat in rows_db:
        status_cls = "status-" + task.status
        opts = "".join(
            f"<option value='{s}' {'selected' if s == task.status else ''}>{s}</option>"
            for s in STATUS_OPTIONS
        )
        rows += f"""<tr>
          <td>{_badge(task.task_type)}</td>
          <td>{_badge(task.status, status_cls)}</td>
          <td class="prio-{task.priority}">{task.priority}</td>
          <td>{_badge(f'{task.opportunity_score:.0f}', _opp_class(task.opportunity_score))}</td>
          <td>{_badge(f'{task.risk_score:.0f}', _risk_class(task.risk_score))}</td>
          <td class="url-cell"><a href="{plat.url}" target="_blank">{plat.title}</a></td>
          <td class="text-cell">{(task.message_draft or '')[:80]}</td>
          <td>
            <form method="post" action="/gui/task-status" style="display:flex;gap:4px">
              <input type="hidden" name="task_id" value="{task.id}">
              <select name="status" style="width:120px">{opts}</select>
              <button class="btn btn-primary btn-sm" type="submit">&#10003;</button>
            </form>
          </td>
        </tr>"""

    body = f"""<div class="card">
      <h2>&#9989; Задачи (топ 100 по скору)</h2>
      <div class="tbl-wrap"><table>
        <thead><tr><th>Тип</th><th>Статус</th><th>Приор.</th><th>Opp</th><th>Risk</th><th>Площадка</th><th>Черновик</th><th>Действие</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=8 style="text-align:center;color:var(--text-muted)">Нет задач</td></tr>'}</tbody>
      </table></div></div>"""
    return _page("Задачи", body, active="t", flash=flash)


# ---------------------------------------------------------------------------
# Mentions
# ---------------------------------------------------------------------------

@router.get("/mentions", response_class=HTMLResponse)
def mentions_page() -> str:
    with SessionLocal() as session:
        rows_db = session.execute(
            select(Mention).order_by(Mention.collected_at.desc()).limit(100)
        ).scalars().all()

    rows = ""
    for m in rows_db:
        intents = ", ".join(m.detected_intents or [])
        rows += f"""<tr>
          <td class="url-cell"><a href="{m.source_url}" target="_blank">{m.source_url}</a></td>
          <td class="text-cell">{(m.text or '')[:150]}</td>
          <td>{intents or '—'}</td>
          <td style="font-size:11px;color:var(--text-muted)">{m.collected_at.strftime('%d.%m %H:%M') if m.collected_at else ''}</td>
        </tr>"""

    body = f"""<div class="card">
      <h2>&#128172; Упоминания (последние 100)</h2>
      <div class="tbl-wrap"><table>
        <thead><tr><th>URL</th><th>Текст</th><th>Интенты</th><th>Дата сбора</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=4 style="text-align:center;color:var(--text-muted)">Нет данных</td></tr>'}</tbody>
      </table></div></div>"""
    return _page("Упоминания", body, active="m")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.get("/settings", response_class=HTMLResponse)
def settings_page(flash: str = "") -> str:
    cfg = _load_settings()
    db_info = _db_url.split("@")[-1] if "@" in _db_url else _db_url[:60]

    def val(key: str, default: str = "") -> str:
        v = cfg.get(key, os.environ.get(key.upper(), default))
        return str(v).replace('"', "&quot;")

    body = f"""
    <div class="card">
      <h2>&#9881;&#65039; Настройки интеграций</h2>
      <p style="margin-bottom:16px;color:var(--text-muted);font-size:13px">
        База данных: <code>{db_info}</code>
      </p>
      <form method="post" action="/gui/save-settings">
        <div class="form-grid">
          <div class="form-row">
            <label>Airtable PAT</label>
            <input type="password" name="airtable_pat" value="{val('airtable_pat')}" placeholder="pat_...">
          </div>
          <div class="form-row">
            <label>Airtable Base ID</label>
            <input type="text" name="airtable_base_id" value="{val('airtable_base_id')}" placeholder="app...">
          </div>
          <div class="form-row">
            <label>Notion Token</label>
            <input type="password" name="notion_token" value="{val('notion_token')}" placeholder="secret_...">
          </div>
          <div class="form-row">
            <label>Notion Tasks DB ID</label>
            <input type="text" name="notion_tasks_db_id" value="{val('notion_tasks_db_id')}">
          </div>
          <div class="form-row">
            <label>Telegram Bot Token</label>
            <input type="password" name="telegram_bot_token" value="{val('telegram_bot_token')}" placeholder="12345:ABC...">
          </div>
          <div class="form-row">
            <label>Telegram Operator Chat ID</label>
            <input type="text" name="telegram_operator_chat_id" value="{val('telegram_operator_chat_id')}" placeholder="-100...">
          </div>
          <div class="form-row">
            <label>VK Access Token</label>
            <input type="password" name="vk_access_token" value="{val('vk_access_token')}">
          </div>
          <div class="form-row">
            <label>Google Spreadsheet ID</label>
            <input type="text" name="google_spreadsheet_id" value="{val('google_spreadsheet_id')}">
          </div>
        </div>
        <hr style="margin:20px 0;border-color:var(--border)">
        <h3 style="margin-bottom:10px">&#128269; Источники для сканирования</h3>
        <p style="color:var(--text-muted);font-size:12px;margin-bottom:10px">
          Telegram каналы — по одному имени на строку, без @. Программа заходит на публичную
          страницу t.me/s/ИМЯ и ищет посты студентов. Каналы должны быть публичными.
        </p>
        <div class="form-row" style="flex-direction:column;align-items:flex-start;gap:6px">
          <label>Telegram каналы (по одному на строку)</label>
          <textarea name="tg_channels" rows="8" style="width:100%;font-family:monospace;font-size:13px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);resize:vertical">{val('tg_channels', chr(10).join(["studizba","student_helper_ru","diplomchik_help","kursovik_help","nauka_pomoshch","antiplagiat_help","vkr_diplom","referat_kursovaya","student_rf","ucheba_legko"]))}</textarea>
        </div>
        <button class="btn btn-primary" type="submit" style="margin-top:12px">&#128190; Сохранить настройки</button>
      </form>
    </div>
    <div class="card" style="margin-top:0">
      <h2>&#128190; Экспорт данных</h2>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <a class="btn btn-ghost" href="/api/export/csv?table=platforms">&#8659; platforms.csv</a>
        <a class="btn btn-ghost" href="/api/export/csv?table=tasks">&#8659; tasks.csv</a>
        <a class="btn btn-ghost" href="/api/export/csv?table=mentions">&#8659; mentions.csv</a>
        <a class="btn btn-ghost" href="/api/export/ndjson?table=platforms">&#8659; platforms.ndjson</a>
        <a class="btn btn-ghost" href="/api/export/ndjson?table=tasks">&#8659; tasks.ndjson</a>
      </div>
    </div>"""
    return _page("Настройки", body, active="s", flash=flash)


@router.post("/gui/save-settings")
def save_settings(
    airtable_pat: str = Form(""),
    airtable_base_id: str = Form(""),
    notion_token: str = Form(""),
    notion_tasks_db_id: str = Form(""),
    telegram_bot_token: str = Form(""),
    telegram_operator_chat_id: str = Form(""),
    vk_access_token: str = Form(""),
    google_spreadsheet_id: str = Form(""),
    tg_channels: str = Form(""),
) -> RedirectResponse:
    data = {
        "airtable_pat": airtable_pat,
        "airtable_base_id": airtable_base_id,
        "notion_token": notion_token,
        "notion_tasks_db_id": notion_tasks_db_id,
        "telegram_bot_token": telegram_bot_token,
        "telegram_operator_chat_id": telegram_operator_chat_id,
        "vk_access_token": vk_access_token,
        "google_spreadsheet_id": google_spreadsheet_id,
        "tg_channels": tg_channels,
    }
    # Save all fields including empty ones so they overwrite previous values
    _save_settings({k: v for k, v in data.items() if v})
    # Persist to environment for current process
    for k, v in data.items():
        if v:
            os.environ[k.upper()] = v
    return RedirectResponse(url="/settings?flash=Настройки+сохранены", status_code=303)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@router.post("/gui/run-discovery")
def run_discovery_gui() -> RedirectResponse:
    threading.Thread(target=run_discovery, daemon=True).start()
    return RedirectResponse(url="/?flash=Discovery+запущен+в+фоне", status_code=303)


@router.get("/gui/trigger-scan")
def trigger_scan_gui() -> RedirectResponse:
    threading.Thread(target=run_trigger_scan, daemon=True).start()
    return RedirectResponse(url="/platforms?flash=Триггер-скан+запущен+в+фоне", status_code=303)


@router.post("/gui/task-status")
def update_task_status_gui(task_id: str = Form(...), status: str = Form(...)) -> RedirectResponse:
    if status not in STATUS_OPTIONS:
        return RedirectResponse(url="/tasks", status_code=303)
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task:
            task.status = status
            session.add(task)
            session.commit()
    return RedirectResponse(url="/tasks?flash=Статус+обновлён", status_code=303)


# ---------------------------------------------------------------------------
# In-app CSV / NDJSON download (no file system required)
# ---------------------------------------------------------------------------

@router.get("/api/export/csv")
def export_csv(table: str = "platforms"):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    allowed = {"platforms", "tasks", "mentions", "competitors"}
    if table not in allowed:
        return JSONResponse({"error": "invalid table"}, status_code=400)

    buf = io.StringIO()
    writer = csv.writer(buf)

    with SessionLocal() as session:
        if table == "platforms":
            rows = session.execute(select(Platform)).scalars().all()
            writer.writerow(["id", "platform_type", "title", "url", "audience_size", "commercial_tolerance"])
            for p in rows:
                writer.writerow([p.id, p.platform_type, p.title, p.url, p.audience_size, p.commercial_tolerance])
        elif table == "tasks":
            rows = session.execute(select(Task)).scalars().all()
            writer.writerow(["id", "task_type", "status", "priority", "opportunity_score", "risk_score", "utm_campaign"])
            for t in rows:
                writer.writerow([t.id, t.task_type, t.status, t.priority, t.opportunity_score, t.risk_score, t.utm_campaign])
        elif table == "mentions":
            rows = session.execute(select(Mention)).scalars().all()
            writer.writerow(["id", "source_url", "text", "detected_intents"])
            for m in rows:
                writer.writerow([m.id, m.source_url, (m.text or "")[:300], m.detected_intents])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}.csv"},
    )


@router.get("/api/export/ndjson")
def export_ndjson(table: str = "platforms"):
    import io
    from fastapi.responses import StreamingResponse

    allowed = {"platforms", "tasks"}
    if table not in allowed:
        return JSONResponse({"error": "invalid table"}, status_code=400)

    with SessionLocal() as session:
        if table == "platforms":
            rows = session.execute(select(Platform)).scalars().all()
            lines = [
                json.dumps({"id": str(p.id), "platform_type": p.platform_type, "title": p.title,
                            "url": p.url, "tags": p.tags, "audience_size": p.audience_size},
                           ensure_ascii=False)
                for p in rows
            ]
        else:
            rows = session.execute(select(Task)).scalars().all()
            lines = [
                json.dumps({"id": str(t.id), "task_type": t.task_type, "status": t.status,
                            "opportunity_score": t.opportunity_score, "risk_score": t.risk_score,
                            "utm_campaign": t.utm_campaign}, ensure_ascii=False)
                for t in rows
            ]

    content = "\n".join(lines) + "\n"
    return StreamingResponse(
        iter([content]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename={table}.ndjson"},
    )
