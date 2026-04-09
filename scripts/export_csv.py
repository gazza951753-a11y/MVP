"""Export DB data to CSV and NDJSON formats.

Output directory: ./export/

Files produced:
  platforms.csv / platforms.ndjson
  competitors.csv / competitors.ndjson
  mentions.csv / mentions.ndjson
  tasks.csv / tasks.ndjson

CSV spec follows the field list in the technical specification.
NDJSON (newline-delimited JSON) is suitable for streaming / LLM tools.

Usage::

    python scripts/export_csv.py [--format csv|ndjson|both] [--out-dir ./export]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import Competitor, Mention, Platform, Task


def _platform_row(p: Platform) -> dict:
    return {
        "id": str(p.id),
        "platform_type": p.platform_type,
        "title": p.title,
        "url": p.url,
        "handle": p.handle or "",
        "language": p.language or "",
        "geo": p.geo or "",
        "audience_size": p.audience_size or "",
        "commercial_tolerance": p.commercial_tolerance,
        "tags": json.dumps(p.tags, ensure_ascii=False),
        "risk_flags": json.dumps(p.risk_flags, ensure_ascii=False),
        "discovery_source": p.discovery_source,
        "created_at": p.created_at.isoformat() if p.created_at else "",
    }


def _competitor_row(c: Competitor) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "normalized_name": c.normalized_name,
        "website_url": c.website_url or "",
        "category": c.category,
        "geo": c.geo or "",
        "pricing_model": c.pricing_model or "",
        "confidence": c.confidence,
        "discovered_from": c.discovered_from,
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }


def _mention_row(m: Mention) -> dict:
    return {
        "id": str(m.id),
        "platform_id": str(m.platform_id),
        "mention_type": m.mention_type,
        "source_url": m.source_url,
        "author_handle": m.author_handle or "",
        "text": (m.text or "")[:500],
        "detected_intents": json.dumps(m.detected_intents, ensure_ascii=False),
        "trigger_hits": json.dumps(m.trigger_hits, ensure_ascii=False),
        "fingerprint": m.fingerprint,
        "collected_at": m.collected_at.isoformat() if m.collected_at else "",
    }


def _task_row(t: Task) -> dict:
    return {
        "id": str(t.id),
        "task_type": t.task_type,
        "status": t.status,
        "priority": t.priority,
        "opportunity_score": t.opportunity_score,
        "risk_score": t.risk_score,
        "recommended_action": t.recommended_action or "",
        "message_draft": (t.message_draft or "")[:300],
        "utm_campaign": t.utm_campaign or "",
        "platform_id": str(t.platform_id),
        "mention_id": str(t.mention_id) if t.mention_id else "",
        "reviewer_verdict": t.reviewer_verdict or "",
        "created_at": t.created_at.isoformat() if t.created_at else "",
    }


# --------------------------------------------------------------------------- #
# Writers                                                                      #
# --------------------------------------------------------------------------- #

def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_ndjson(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Export functions                                                             #
# --------------------------------------------------------------------------- #

def export_platforms(out_dir: Path, fmt: str) -> int:
    with SessionLocal() as session:
        rows = [_platform_row(p) for p in session.execute(select(Platform)).scalars()]
    if fmt in ("csv", "both"):
        _write_csv(out_dir / "platforms.csv", rows)
    if fmt in ("ndjson", "both"):
        _write_ndjson(out_dir / "platforms.ndjson", rows)
    return len(rows)


def export_competitors(out_dir: Path, fmt: str) -> int:
    with SessionLocal() as session:
        rows = [_competitor_row(c) for c in session.execute(select(Competitor)).scalars()]
    if fmt in ("csv", "both"):
        _write_csv(out_dir / "competitors.csv", rows)
    if fmt in ("ndjson", "both"):
        _write_ndjson(out_dir / "competitors.ndjson", rows)
    return len(rows)


def export_mentions(out_dir: Path, fmt: str) -> int:
    with SessionLocal() as session:
        rows = [_mention_row(m) for m in session.execute(select(Mention)).scalars()]
    if fmt in ("csv", "both"):
        _write_csv(out_dir / "mentions.csv", rows)
    if fmt in ("ndjson", "both"):
        _write_ndjson(out_dir / "mentions.ndjson", rows)
    return len(rows)


def export_tasks(out_dir: Path, fmt: str) -> int:
    with SessionLocal() as session:
        rows = [_task_row(t) for t in session.execute(select(Task)).scalars()]
    if fmt in ("csv", "both"):
        _write_csv(out_dir / "tasks.csv", rows)
    if fmt in ("ndjson", "both"):
        _write_ndjson(out_dir / "tasks.ndjson", rows)
    return len(rows)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Export DB data to CSV/NDJSON")
    parser.add_argument("--format", choices=["csv", "ndjson", "both"], default="both")
    parser.add_argument("--out-dir", default="export")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = args.format

    counts = {
        "platforms": export_platforms(out_dir, fmt),
        "competitors": export_competitors(out_dir, fmt),
        "mentions": export_mentions(out_dir, fmt),
        "tasks": export_tasks(out_dir, fmt),
    }

    print(f"Exports written to {out_dir}/ [{fmt}]")
    for entity, n in counts.items():
        print(f"  {entity}: {n} rows")


if __name__ == "__main__":
    main()
