#!/usr/bin/env bash
# v10.1.0 release cutover helper (run on Widow after merge to main).
set -euo pipefail

REPO="${REPO:-/opt/news-intelligence}"
TAG="${TAG:-v10.1.0}"

echo "=== News Intelligence ${TAG} cutover ==="
echo "Repo: ${REPO}"
echo "Stop API..."
sudo systemctl stop news-intelligence-api-public.service

cd "${REPO}"
git fetch origin
git checkout "${TAG}"

echo "Run migrations 246-256 (direct Postgres :5432)..."
export DB_MAINTENANCE_PORT=5432 DB_PORT=5432
for m in 246 247 248 249 250 251 252 253 254 255 256; do
  PYTHONPATH=api python api/scripts/run_migration.py "${m}"
done

echo "Verify registry, SSOT, and v10.1 wiring..."
python scripts/verify_feature_registry.py
python scripts/verify_single_source_of_truth.py
PYTHONPATH=api python api/scripts/verify_v10_1_wiring.py
PYTHONPATH=api python scripts/verify_orchestrator_pipeline_connectivity.py

echo "Start API..."
sudo systemctl start news-intelligence-api-public.service
sleep 4
systemctl is-active news-intelligence-api-public.service

curl -sf http://127.0.0.1:8000/ | python3 -c "import sys,json; d=json.load(sys.stdin); print('version', d.get('data',{}).get('version'))"

echo "Run intake ratio baseline..."
PYTHONPATH=api python api/scripts/intake_processing_ratio.py

echo "=== Cutover complete. Monitor net_growth for 7 days before declaring stable. ==="
