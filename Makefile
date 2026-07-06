# Container builds for the RS Recruitment services.
#
# Uses Docker Buildx (BuildKit). The service Dockerfiles use a uv cache mount
# (RUN --mount=type=cache) so dependency wheels are reused across builds without
# bloating the images — this REQUIRES BuildKit/buildx (the legacy builder errors
# on --mount). Install locally with `docker buildx install` or the buildx plugin;
# in CI use docker/setup-buildx-action.
#
# The base image must be built first; the api and worker images build FROM it.
# Build context is always the repo root (the service Dockerfiles reach into
# libs/shared and the workspace manifests).

IMAGE_TAG ?= local
BASE_IMAGE ?= rs-recruiting-base:$(IMAGE_TAG)
BUILD ?= docker buildx build --load

.PHONY: images base api worker up services down logs check

# Full local validation with CI parity: everything ci.yml enforces, in one
# target. Agents and the pre-PR checklist delegate here so the list of checks
# has a single source of truth. (The claude-hooks self-test is local-only —
# it guards the .claude/hooks/ guard rails against silent rot.)
check:
	bash scripts/test_claude_hooks.sh
	uv run ruff check .
	uv run ruff format --check .
	uv run lint-imports
	uv run python scripts/validate_imports.py
	uv run python scripts/check_file_sizes.py
	uv run python scripts/validate_type_hints.py
	uv run python scripts/validate_blocking_io.py
	uv run python scripts/validate_test_files.py
	cd frontend && npx tsc --noEmit && npm run lint && npm test
	uv run pytest -n auto -q

# Build every service image (base first).
images: base api worker

# Full containerized stack: backing services + the api + worker images (the
# `app` profile). Builds images first, since compose doesn't build the base.
up: images
	docker compose --profile app up -d

# Backing services only (db + mailpit + localstack) — for the `uvicorn --reload`
# backend inner loop. No image build needed.
services:
	docker compose up -d

# Stops everything (containers in all profiles).
down:
	docker compose --profile app down

logs:
	docker compose logs -f api worker

base:
	$(BUILD) -f docker/base.Dockerfile -t $(BASE_IMAGE) .

api: base
	$(BUILD) -f services/api/Dockerfile \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) \
		-t rs-recruiting-api:$(IMAGE_TAG) .

worker: base
	$(BUILD) -f services/worker/Dockerfile \
		--build-arg BASE_IMAGE=$(BASE_IMAGE) \
		-t rs-recruiting-worker:$(IMAGE_TAG) .
