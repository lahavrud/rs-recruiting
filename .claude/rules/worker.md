# Task Queue & Worker Rules

Applies to `libs/shared/rs_shared/core/tasks.py`, `.../core/task_contract.py`,
`.../core/matching.py`, and `services/worker/rs_worker/`.

## Wire contract

`task_contract.py` defines the SQS message format once (`TaskName` constants +
`build_*_message` / `decode_message`) and is imported by **both** the producer
(api) and the consumer (worker). Never construct or parse task messages ad hoc —
always go through the contract module, and change producer + consumer sides in
the same PR. Remember the two services deploy as separate images: during a
rolling deploy old-format messages can still be in flight, so message-format
changes must be consumed-side backward-compatible.

## Delivery semantics

- SQS is **at-least-once** → every task must be **idempotent**. Pattern:
  `build_data_export_task` no-ops when a pending export already exists.
- The worker deletes a message only on success; on exception the message is
  redelivered and eventually lands in the DLQ. **Let failures propagate** — a
  swallowed exception acks the message and silently loses the work.
- The worker handles `SIGTERM` by finishing the in-flight batch; keep tasks
  short enough that a visibility-timeout redelivery is unlikely.

## Local-dev asymmetry

When `SQS_QUEUE_URL` is unset (local dev), `enqueue_*` runs the task inline in
the api process. Don't rely on queue semantics (ordering, retry, DLQ) in local
testing — they only exist with a real/localstack queue.

## Adding a task

1. `TaskName` constant + `build_*_message` in `task_contract.py`
2. Task function + `TASK_REGISTRY` entry in `tasks.py` (or `matching.py`)
3. `enqueue_*` producer function in `tasks.py`
4. Tests for both producer and consumer sides (fake SQS lives in `tests/conftest.py`)

## Boundaries

`rs_worker` and `rs_shared` must stay web-stack-free (no fastapi/uvicorn/slowapi).
Enforced by import-linter contracts (root `pyproject.toml`) and
`tests/test_domain_is_framework_free.py` — add worker deps with
`uv add <pkg> --package rs-recruiting-worker`, never to shared unless both
services truly need it.
