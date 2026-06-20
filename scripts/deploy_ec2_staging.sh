#!/bin/bash
# Ephemeral staging deploy — runs on the staging EC2 via SSM Run Command.
#
# Deliberately separate from deploy_ec2.sh (production) rather than branching it:
# staging diverges enough (no Grafana/observability, no CloudFront, nginx serves
# the frontend, fresh DB + mock-data seed every cycle, no blue/green SHA
# tracking or rollback) that keeping the prod-critical script untouched is safer
# than threading an ENVIRONMENT flag through it.
#
# The box is thrown away each cycle, so there's no CURRENT_SHA/PREV_SHA state and
# no rollback: if the deploy fails, the run fails and the environment is
# recreated on the next RC.
set -euo pipefail

ENVIRONMENT="staging"
APP_DIR="/home/ec2-user/app"
REGION="us-east-1"

if [[ -z "${IMAGE_TAG:-}" ]]; then
  echo "ERROR: IMAGE_TAG is required (the RC tag being staged)."
  exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
S3_BUCKET="rs-recruiting-deploy-${ENVIRONMENT}-${ACCOUNT_ID}"
export IMAGE_TAG

# This box's Elastic IP (IMDSv2) — the app needs an absolute, non-localhost
# FRONTEND_BASE_URL (config.validate_settings enforces this in staging), and the
# IP changes each cycle so it can't be a static SSM param. SSM has higher source
# precedence than env in deployed environments (see config.settings_customise_
# sources), so deliberately do NOT seed these in SSM — env is the right layer.
IMDS_TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" \
  http://169.254.169.254/latest/meta-data/public-ipv4)
export FRONTEND_BASE_URL="http://${PUBLIC_IP}/"
export ALLOWED_ORIGINS="http://${PUBLIC_IP}"

echo "==> ECR registry: ${ECR_REGISTRY}"
echo "==> S3 bucket:    ${S3_BUCKET}"
echo "==> IMAGE_TAG:    ${IMAGE_TAG}"
echo "==> Public URL:   ${FRONTEND_BASE_URL}"

# Ephemeral staging provisions a fresh box each cycle, and staging-apply
# dispatches this deploy the moment tofu finishes — which can race cloud-init/
# user-data still installing Docker and the compose v2 plugin. Wait for both
# before proceeding, else `docker compose` exits 125 ("unknown command").
echo "==> Waiting for Docker + compose plugin (cloud-init may still be running)"
for _ in $(seq 1 60); do
  if docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
if ! { docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; }; then
  echo "ERROR: Docker/compose not ready after 5 minutes"
  exit 1
fi

echo "==> Logging in to ECR"
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "==> Fetching deploy artifacts"
mkdir -p "${APP_DIR}"
COMPOSE_FILE="${APP_DIR}/docker-compose.staging.yml"
aws s3 cp "s3://${S3_BUCKET}/deploy/${IMAGE_TAG}/docker-compose.staging.yml" "${COMPOSE_FILE}"
aws s3 cp "s3://${S3_BUCKET}/deploy/${IMAGE_TAG}/nginx.staging.conf" "${APP_DIR}/nginx.staging.conf"

echo "==> Unpacking frontend bundle"
rm -rf "${APP_DIR}/dist"
mkdir -p "${APP_DIR}/dist"
aws s3 cp "s3://${S3_BUCKET}/deploy/${IMAGE_TAG}/frontend-dist.tar.gz" "${APP_DIR}/frontend-dist.tar.gz"
tar -xzf "${APP_DIR}/frontend-dist.tar.gz" -C "${APP_DIR}/dist"

echo "==> Pulling Docker images"
docker compose -f "${COMPOSE_FILE}" pull

echo "==> Stopping existing stack"
docker compose -f "${COMPOSE_FILE}" down --timeout 30 || true

echo "==> Validating migration chain (must be exactly one head)"
HEAD_COUNT=$(docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api \
  alembic heads 2>&1 | grep -c "(head)" || true)
if [ "${HEAD_COUNT}" -ne 1 ]; then
  echo "ERROR: alembic reports ${HEAD_COUNT} head(s) — expected exactly 1."
  docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api alembic heads
  exit 1
fi

# Staging provisions a brand-new RDS each cycle. The app's 40 Alembic migrations
# are incremental-only — they ALTER a base schema that was originally built by
# SQLModel.metadata.create_all() (see src/core/infrastructure/database.py:init_db),
# with Alembic adopted later to evolve the existing prod DB. So `alembic upgrade
# head` against an EMPTY database fails on the first ALTER. Bootstrap the way the
# app and the test suite do (tests/conftest.py): build the schema from the models,
# then stamp Alembic at head. Do NOT switch this back to `upgrade head`.
echo "==> Building schema from models (create_all)"
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api \
  python -c "import asyncio; from src.core.infrastructure.database import init_db; asyncio.run(init_db())"

echo "==> Stamping Alembic at head"
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api alembic stamp head

echo "==> Seeding mock data"
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api \
  python scripts/seed_mock_data.py --reset

echo "==> Starting services"
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

echo "==> Restarting nginx (refreshes upstream API IP)"
docker compose -f "${COMPOSE_FILE}" restart nginx

echo "==> Waiting for api container to become healthy (90s)"
deadline=$(( $(date +%s) + 90 ))
healthy=false
while [[ $(date +%s) -lt $deadline ]]; do
  CONTAINER_ID=$(docker compose -f "${COMPOSE_FILE}" ps -q api 2>/dev/null || echo "")
  if [[ -n "${CONTAINER_ID}" ]]; then
    HC_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_ID}" 2>/dev/null || echo "")
    case "${HC_STATUS}" in
      healthy)   healthy=true; break ;;
      unhealthy) break ;;
    esac
  fi
  sleep 5
done

if ! $healthy; then
  echo "==> Health check FAILED"
  docker compose -f "${COMPOSE_FILE}" logs --tail 50 api || true
  exit 1
fi

echo "==> Staging deploy complete — ${FRONTEND_BASE_URL} (IMAGE_TAG=${IMAGE_TAG})"
