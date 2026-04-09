#!/usr/bin/env bash
set -euo pipefail
# Full nightly discovery: all collectors → DB → tasks.
python -c "
from app.pipeline import run_discovery
import json
result = run_discovery()
print(json.dumps(result, indent=2))
"
