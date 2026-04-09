#!/usr/bin/env bash
set -euo pipefail
# В MVP trigger-scan переиспользует discovery pipeline.
python -c "from app.pipeline import run_discovery; print(run_discovery())"
