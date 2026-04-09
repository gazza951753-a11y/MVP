#!/usr/bin/env bash
set -euo pipefail
# Frequent hot-path trigger scan (run every 10–30 minutes via cron/scheduler).
# Uses a lighter collector set than full discovery.
python -c "
from app.pipeline import run_trigger_scan
import json
result = run_trigger_scan()
print(json.dumps(result, indent=2))
"
