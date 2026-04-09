#!/usr/bin/env bash
set -euo pipefail
python -c "from app.pipeline import run_discovery; print(run_discovery())"
