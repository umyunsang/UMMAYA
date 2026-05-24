#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Idempotently prepare GCP resources for the UMMAYA live adapter gateway.

set -euo pipefail

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "bootstrap-live-gateway: missing required environment variable: ${name}" >&2
    exit 2
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "bootstrap-live-gateway: missing required command: $1" >&2
    exit 2
  fi
}

require_env GCP_PROJECT_ID
require_env GCP_REGION
require_env GITHUB_REPOSITORY
require_command gcloud

SEED_SECRETS="${GCP_SEED_SECRETS:-1}"
if [[ "${SEED_SECRETS}" == "1" ]]; then
  require_env UMMAYA_DATA_GO_KR_API_KEY
  require_env UMMAYA_KMA_API_HUB_AUTH_KEY
  require_env UMMAYA_KAKAO_API_KEY
  require_env UMMAYA_JUSO_CONFM_KEY
  require_env UMMAYA_SGIS_KEY
  require_env UMMAYA_SGIS_SECRET
fi

REPOSITORY="${GCP_ARTIFACT_REGISTRY_REPOSITORY:-ummaya}"
RUN_SERVICE="${GCP_RUN_SERVICE:-ummaya-live-gateway}"
RUNTIME_SA_NAME="${GCP_RUN_RUNTIME_SERVICE_ACCOUNT_NAME:-ummaya-live-gateway-runtime}"
DEPLOY_SA_NAME="${GCP_DEPLOY_SERVICE_ACCOUNT_NAME:-ummaya-live-gateway-deployer}"
WIF_POOL="${GCP_WORKLOAD_IDENTITY_POOL:-github}"
WIF_PROVIDER="${GCP_WORKLOAD_IDENTITY_PROVIDER_ID:-ummaya}"

RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
DEPLOY_SA_EMAIL="${DEPLOY_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

DATA_GO_KR_SECRET="${GCP_SECRET_DATA_GO_KR_API_KEY:-ummaya-data-go-kr-api-key}"
KMA_API_HUB_SECRET="${GCP_SECRET_KMA_API_HUB_AUTH_KEY:-ummaya-kma-api-hub-auth-key}"
KAKAO_SECRET="${GCP_SECRET_KAKAO_API_KEY:-ummaya-kakao-api-key}"
JUSO_SECRET="${GCP_SECRET_JUSO_CONFM_KEY:-ummaya-juso-confm-key}"
SGIS_KEY_SECRET="${GCP_SECRET_SGIS_KEY:-ummaya-sgis-key}"
SGIS_SECRET_SECRET="${GCP_SECRET_SGIS_SECRET:-ummaya-sgis-secret}"
GATEWAY_TOKEN_SECRET="${GCP_SECRET_LIVE_ADAPTER_GATEWAY_TOKEN:-ummaya-live-adapter-gateway-token}"
GATEWAY_TOKEN_FOR_CI="${GCP_SET_GATEWAY_TOKEN_VARIABLE:-0}"

echo "bootstrap-live-gateway: enabling required Google APIs"
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iamcredentials.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  sts.googleapis.com \
  --project "${GCP_PROJECT_ID}"

project_number="$(gcloud projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)')"
cloudbuild_sa="${project_number}@cloudbuild.gserviceaccount.com"

if ! gcloud artifacts repositories describe "${REPOSITORY}" \
  --project "${GCP_PROJECT_ID}" \
  --location "${GCP_REGION}" >/dev/null 2>&1; then
  echo "bootstrap-live-gateway: creating Artifact Registry repository ${REPOSITORY}"
  gcloud artifacts repositories create "${REPOSITORY}" \
    --project "${GCP_PROJECT_ID}" \
    --location "${GCP_REGION}" \
    --repository-format docker \
    --description "UMMAYA live adapter gateway images"
fi

create_service_account() {
  local name="$1"
  local display_name="$2"
  if ! gcloud iam service-accounts describe "${name}@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --project "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo "bootstrap-live-gateway: creating service account ${name}"
    gcloud iam service-accounts create "${name}" \
      --project "${GCP_PROJECT_ID}" \
      --display-name "${display_name}"
  fi
}

create_service_account "${RUNTIME_SA_NAME}" "UMMAYA live gateway runtime"
create_service_account "${DEPLOY_SA_NAME}" "UMMAYA live gateway deployer"

echo "bootstrap-live-gateway: granting IAM roles"
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member "serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role roles/secretmanager.secretAccessor \
  --condition=None >/dev/null

for role in roles/run.admin roles/artifactregistry.writer roles/cloudbuild.builds.editor; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member "serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role "${role}" \
    --condition=None >/dev/null
done

gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member "serviceAccount:${cloudbuild_sa}" \
  --role roles/artifactregistry.writer \
  --condition=None >/dev/null

gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SA_EMAIL}" \
  --project "${GCP_PROJECT_ID}" \
  --member "serviceAccount:${DEPLOY_SA_EMAIL}" \
  --role roles/iam.serviceAccountUser >/dev/null

create_or_seed_secret() {
  local secret_name="$1"
  local env_name="$2"
  if ! gcloud secrets describe "${secret_name}" --project "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo "bootstrap-live-gateway: creating Secret Manager secret ${secret_name}"
    gcloud secrets create "${secret_name}" \
      --project "${GCP_PROJECT_ID}" \
      --replication-policy automatic >/dev/null
  fi
  if [[ "${SEED_SECRETS}" != "1" ]]; then
    echo "bootstrap-live-gateway: seed disabled; secret ${secret_name} exists but no version was added"
    return
  fi
  if [[ -n "${!env_name:-}" ]]; then
    echo "bootstrap-live-gateway: adding new version for ${secret_name} from ${env_name}"
    printf '%s' "${!env_name}" | gcloud secrets versions add "${secret_name}" \
      --project "${GCP_PROJECT_ID}" \
      --data-file=- >/dev/null
  else
    echo "bootstrap-live-gateway: ${env_name} is unset; secret ${secret_name} exists but was not seeded"
  fi
}

create_or_seed_secret "${DATA_GO_KR_SECRET}" UMMAYA_DATA_GO_KR_API_KEY
create_or_seed_secret "${KMA_API_HUB_SECRET}" UMMAYA_KMA_API_HUB_AUTH_KEY
create_or_seed_secret "${KAKAO_SECRET}" UMMAYA_KAKAO_API_KEY
create_or_seed_secret "${JUSO_SECRET}" UMMAYA_JUSO_CONFM_KEY
create_or_seed_secret "${SGIS_KEY_SECRET}" UMMAYA_SGIS_KEY
create_or_seed_secret "${SGIS_SECRET_SECRET}" UMMAYA_SGIS_SECRET
if [[ -n "${UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN:-}" ]]; then
  create_or_seed_secret "${GATEWAY_TOKEN_SECRET}" UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN
fi

if ! gcloud iam workload-identity-pools describe "${WIF_POOL}" \
  --project "${GCP_PROJECT_ID}" \
  --location global >/dev/null 2>&1; then
  echo "bootstrap-live-gateway: creating Workload Identity Pool ${WIF_POOL}"
  gcloud iam workload-identity-pools create "${WIF_POOL}" \
    --project "${GCP_PROJECT_ID}" \
    --location global \
    --display-name "GitHub Actions"
fi

if ! gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER}" \
  --project "${GCP_PROJECT_ID}" \
  --location global \
  --workload-identity-pool "${WIF_POOL}" >/dev/null 2>&1; then
  echo "bootstrap-live-gateway: creating OIDC provider ${WIF_PROVIDER}"
  gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER}" \
    --project "${GCP_PROJECT_ID}" \
    --location global \
    --workload-identity-pool "${WIF_POOL}" \
    --display-name "UMMAYA GitHub repository" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition "assertion.repository == '${GITHUB_REPOSITORY}'"
fi

wif_provider_name="projects/${project_number}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"
wif_member="principalSet://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_REPOSITORY}"

gcloud iam service-accounts add-iam-policy-binding "${DEPLOY_SA_EMAIL}" \
  --project "${GCP_PROJECT_ID}" \
  --member "${wif_member}" \
  --role roles/iam.workloadIdentityUser >/dev/null

cat <<EOF
bootstrap-live-gateway: complete

Set these GitHub environment/repository variables for .github/workflows/deploy-live-gateway.yml:

GCP_PROJECT_ID=${GCP_PROJECT_ID}
GCP_REGION=${GCP_REGION}
GCP_ARTIFACT_REGISTRY_REPOSITORY=${REPOSITORY}
GCP_RUN_SERVICE=${RUN_SERVICE}
GCP_RUN_RUNTIME_SERVICE_ACCOUNT=${RUNTIME_SA_EMAIL}
GCP_WORKLOAD_IDENTITY_PROVIDER=${wif_provider_name}
GCP_DEPLOY_SERVICE_ACCOUNT=${DEPLOY_SA_EMAIL}
GCP_SECRET_DATA_GO_KR_API_KEY=${DATA_GO_KR_SECRET}
GCP_SECRET_KAKAO_API_KEY=${KAKAO_SECRET}
GCP_SECRET_JUSO_CONFM_KEY=${JUSO_SECRET}
GCP_SECRET_SGIS_KEY=${SGIS_KEY_SECRET}
GCP_SECRET_SGIS_SECRET=${SGIS_SECRET_SECRET}
EOF

if [[ "${GATEWAY_TOKEN_FOR_CI}" == "1" ]]; then
  cat <<EOF
GCP_SECRET_LIVE_ADAPTER_GATEWAY_TOKEN=${GATEWAY_TOKEN_SECRET}
EOF
fi

if [[ "${GITHUB_SET_VARIABLES:-0}" == "1" ]]; then
  require_command gh
  gh variable set GCP_PROJECT_ID --body "${GCP_PROJECT_ID}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_REGION --body "${GCP_REGION}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_ARTIFACT_REGISTRY_REPOSITORY --body "${REPOSITORY}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_RUN_SERVICE --body "${RUN_SERVICE}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_RUN_RUNTIME_SERVICE_ACCOUNT --body "${RUNTIME_SA_EMAIL}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --body "${wif_provider_name}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --body "${DEPLOY_SA_EMAIL}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_SECRET_DATA_GO_KR_API_KEY --body "${DATA_GO_KR_SECRET}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_SECRET_KAKAO_API_KEY --body "${KAKAO_SECRET}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_SECRET_JUSO_CONFM_KEY --body "${JUSO_SECRET}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_SECRET_SGIS_KEY --body "${SGIS_KEY_SECRET}" --repo "${GITHUB_REPOSITORY}"
  gh variable set GCP_SECRET_SGIS_SECRET --body "${SGIS_SECRET_SECRET}" --repo "${GITHUB_REPOSITORY}"
  if [[ "${GATEWAY_TOKEN_FOR_CI}" == "1" ]]; then
    gh variable set GCP_SECRET_LIVE_ADAPTER_GATEWAY_TOKEN --body "${GATEWAY_TOKEN_SECRET}" --repo "${GITHUB_REPOSITORY}"
  fi
fi
