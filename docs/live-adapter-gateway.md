# Live Adapter Gateway

UMMAYA release CLIs must not contain Kakao, data.go.kr, JUSO, or SGIS operator
credentials. Packaged clients call an operator-hosted gateway for eligible live
`find` and `locate` adapters; the gateway runs the same adapter registry in
`direct` mode and keeps provider keys in the server runtime.

## Runtime

Local operator run:

```bash
UMMAYA_DATA_GO_KR_API_KEY=<redacted> \
UMMAYA_KMA_API_HUB_AUTH_KEY=<redacted> \
UMMAYA_KAKAO_API_KEY=<redacted> \
uv run --extra gateway ummaya-live-gateway
```

Health check:

```bash
curl http://127.0.0.1:8080/readyz
```

Server-side request guards:

```bash
UMMAYA_LIVE_ADAPTER_GATEWAY_RATE_LIMIT_PER_MINUTE=120
UMMAYA_LIVE_ADAPTER_GATEWAY_MAX_BODY_BYTES=65536
```

Private/self-hosted gateways can require a bearer token:

```bash
UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN=<redacted> \
uv run --extra gateway ummaya-live-gateway
```

The matching client-side setting is `UMMAYA_LIVE_ADAPTER_PROXY_TOKEN`. Public
release clients should not need to set it.

## Container

```bash
docker build -f docker/Dockerfile.gateway -t ummaya-live-gateway .
docker run --rm -p 8080:8080 \
  -e UMMAYA_DATA_GO_KR_API_KEY=<redacted> \
  -e UMMAYA_KMA_API_HUB_AUTH_KEY=<redacted> \
  -e UMMAYA_KAKAO_API_KEY=<redacted> \
  ummaya-live-gateway
```

Cloud Run-compatible hosts must pass the runtime `PORT` variable and require the
container to listen on `0.0.0.0`. `ummaya-live-gateway` follows that contract and
defaults to port `8080` when `PORT` is absent.

## Cloud Run

The repository includes an idempotent bootstrap script, a Cloud Build config,
and a deploy script. Cloud Build is used for the direct script path, so local
Docker is not required.

Bootstrap GCP resources, IAM, Workload Identity Federation, Artifact Registry,
and Secret Manager secret containers:

```bash
GCP_PROJECT_ID=<project-id> \
GCP_REGION=asia-northeast3 \
GITHUB_REPOSITORY=umyunsang/UMMAYA \
UMMAYA_DATA_GO_KR_API_KEY=<redacted> \
UMMAYA_KMA_API_HUB_AUTH_KEY=<redacted> \
UMMAYA_KAKAO_API_KEY=<redacted> \
UMMAYA_JUSO_CONFM_KEY=<redacted> \
UMMAYA_SGIS_KEY=<redacted> \
UMMAYA_SGIS_SECRET=<redacted> \
scripts/bootstrap-live-gateway-cloud-run.sh
```

To prepare infrastructure before every provider key is available, set
`GCP_SEED_SECRETS=0`. This creates IAM, Artifact Registry, Workload Identity
Federation, and Secret Manager containers only. It does not create fake secret
versions, and the gateway will still fail startup until every required secret
has a real value.

Deploy a revision:

```bash
GCP_PROJECT_ID=<project-id> \
GCP_REGION=asia-northeast3 \
GCP_ARTIFACT_REGISTRY_REPOSITORY=ummaya \
GCP_RUN_RUNTIME_SERVICE_ACCOUNT=ummaya-live-gateway-runtime@<project-id>.iam.gserviceaccount.com \
GCP_SECRET_DATA_GO_KR_API_KEY=ummaya-data-go-kr-api-key \
GCP_SECRET_KMA_API_HUB_AUTH_KEY=ummaya-kma-api-hub-auth-key \
GCP_SECRET_KAKAO_API_KEY=ummaya-kakao-api-key \
GCP_SECRET_JUSO_CONFM_KEY=ummaya-juso-confm-key \
GCP_SECRET_SGIS_KEY=ummaya-sgis-key \
GCP_SECRET_SGIS_SECRET=ummaya-sgis-secret \
scripts/deploy-live-gateway-cloud-run.sh
```

The GitHub Actions workflow `.github/workflows/deploy-live-gateway.yml` uses
Google Workload Identity Federation and Artifact Registry. It runs automatically
on `main` when gateway-relevant paths change and also supports manual
`workflow_dispatch` with an optional `image_tag`. Configure these repository or
environment variables before relying on either path:

```text
GCP_PROJECT_ID
GCP_REGION
GCP_ARTIFACT_REGISTRY_REPOSITORY
GCP_RUN_SERVICE
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_DEPLOY_SERVICE_ACCOUNT
GCP_RUN_RUNTIME_SERVICE_ACCOUNT
GCP_SECRET_DATA_GO_KR_API_KEY
GCP_SECRET_KMA_API_HUB_AUTH_KEY
GCP_SECRET_KAKAO_API_KEY
GCP_SECRET_JUSO_CONFM_KEY
GCP_SECRET_SGIS_KEY
GCP_SECRET_SGIS_SECRET
```

Each `GCP_SECRET_*` value is a Secret Manager secret name, not the secret value.
The workflow passes those names to Cloud Run as runtime secret references.
The hosted gateway fails startup unless the complete provider key set is present;
there is no fallback route for missing operator credentials.

## Client Route

Packaged CLI defaults:

```bash
UMMAYA_LIVE_ADAPTER_MODE=auto
UMMAYA_LIVE_ADAPTER_PROXY_URL=https://ummaya-live-gateway-ygjh3ipzqq-du.a.run.app/v1/adapters
```

Source-tree or self-hosted direct debugging:

```bash
UMMAYA_LIVE_ADAPTER_MODE=direct
```

The gateway rejects adapters that are not `adapter_mode="live"`, not
`auth_type="api_key"`, not a `find`/`locate` primitive, or not on the
UMMAYA-controlled provider allowlist.
