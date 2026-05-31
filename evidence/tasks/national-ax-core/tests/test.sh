#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

if uv run python -m ummaya.evidence \
  --source-ref "${UMMAYA_EVIDENCE_SOURCE_REF:-local}" \
  --dataset-ref ummaya/national-ax-core@local \
  --out /tmp/ummaya-evidence-run.json; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi
