#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build and deploy the UMMAYA live adapter gateway to Cloud Run.

set -euo pipefail

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "deploy-live-gateway: missing required environment variable: ${name}" >&2
    exit 2
  fi
}

require_env GCP_PROJECT_ID
require_env GCP_REGION
require_env GCP_ARTIFACT_REGISTRY_REPOSITORY
require_env GCP_SECRET_DATA_GO_KR_API_KEY
require_env GCP_SECRET_KMA_API_HUB_AUTH_KEY
require_env GCP_SECRET_KAKAO_API_KEY
require_env GCP_SECRET_JUSO_CONFM_KEY
require_env GCP_SECRET_SGIS_KEY
require_env GCP_SECRET_SGIS_SECRET

SERVICE="${GCP_RUN_SERVICE:-ummaya-live-gateway}"
RUNTIME_SERVICE_ACCOUNT="${GCP_RUN_RUNTIME_SERVICE_ACCOUNT:-ummaya-live-gateway-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"
TAG="${GCP_IMAGE_TAG:-$(git rev-parse --short=12 HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_ARTIFACT_REGISTRY_REPOSITORY}/ummaya-live-gateway:${TAG}"

secrets=(
  "UMMAYA_DATA_GO_KR_API_KEY=${GCP_SECRET_DATA_GO_KR_API_KEY}:latest"
  "UMMAYA_KMA_API_HUB_AUTH_KEY=${GCP_SECRET_KMA_API_HUB_AUTH_KEY}:latest"
  "UMMAYA_KAKAO_API_KEY=${GCP_SECRET_KAKAO_API_KEY}:latest"
  "UMMAYA_JUSO_CONFM_KEY=${GCP_SECRET_JUSO_CONFM_KEY}:latest"
  "UMMAYA_SGIS_KEY=${GCP_SECRET_SGIS_KEY}:latest"
  "UMMAYA_SGIS_SECRET=${GCP_SECRET_SGIS_SECRET}:latest"
)

if [[ -n "${GCP_SECRET_LIVE_ADAPTER_GATEWAY_TOKEN:-}" ]]; then
  secrets+=("UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN=${GCP_SECRET_LIVE_ADAPTER_GATEWAY_TOKEN}:latest")
fi

IFS=,
secret_arg="${secrets[*]}"
unset IFS

echo "deploy-live-gateway: building ${IMAGE}"
gcloud builds submit \
  --project "${GCP_PROJECT_ID}" \
  --config infra/cloud-run/live-gateway.cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}" \
  .

echo "deploy-live-gateway: deploying ${SERVICE} in ${GCP_REGION}"
gcloud run deploy "${SERVICE}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}" \
  --platform managed \
  --image "${IMAGE}" \
  --allow-unauthenticated \
  --port 8080 \
  --execution-environment gen2 \
  --cpu 1 \
  --memory 1Gi \
  --concurrency "${GCP_RUN_CONCURRENCY:-20}" \
  --min-instances "${GCP_RUN_MIN_INSTANCES:-0}" \
  --max-instances "${GCP_RUN_MAX_INSTANCES:-10}" \
  --service-account "${RUNTIME_SERVICE_ACCOUNT}" \
  --set-env-vars "UMMAYA_ENV=prod,UMMAYA_LIVE_ADAPTER_MODE=direct" \
  --update-secrets "${secret_arg}"

url="$(gcloud run services describe "${SERVICE}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}" \
  --format='value(status.url)')"

echo "deploy-live-gateway: health check ${url}/readyz"
curl -fsS "${url}/readyz"
echo
